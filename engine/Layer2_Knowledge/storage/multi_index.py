"""
Multi-Index Manager - Separate Knowledge Spaces
=================================================
Manages separate vector indexes for different document types.

Key Insight:
Legal questions require precision.
Event questions require context.
Mixing them destroys retrieval accuracy.
"""

from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import os


class KnowledgeSpace(Enum):
    """Types of knowledge spaces."""
    LEGAL = "legal"          # Treaties, laws, agreements, provisions
    EVENT = "event"          # News, statements, press releases
    ECONOMIC = "economic"    # Trade data, sanctions, tariffs
    STRATEGIC = "strategic"  # Analysis, think tank reports


@dataclass
class IndexConfig:
    """Configuration for a knowledge index."""
    name: str
    space: KnowledgeSpace
    collection_name: str
    description: str
    document_types: List[str]
    priority: int = 1


class MultiIndexManager:
    """
    Manages separate vector indexes for each knowledge space.
    
    Why separate indexes?
    1. Legal documents need exact matching
    2. Event documents need recency weighting
    3. Economic data needs numerical precision
    4. Strategic analysis needs context preservation
    
    Usage:
        manager = MultiIndexManager()
        
        # Route a document to appropriate index
        space = manager.route_document(doc)
        manager.add_document(doc, space)
        
        # Search specific spaces
        results = manager.search(
            query="RCEP tariff provisions",
            spaces=[KnowledgeSpace.LEGAL, KnowledgeSpace.ECONOMIC]
        )
    """
    
    # Index configurations
    INDEX_CONFIGS = {
        KnowledgeSpace.LEGAL: IndexConfig(
            name="legal_index",
            space=KnowledgeSpace.LEGAL,
            collection_name="diplomatic_legal",
            description="Treaties, laws, and legal provisions",
            document_types=["treaty", "law", "agreement", "provision", "convention", "protocol"],
            priority=1
        ),
        KnowledgeSpace.EVENT: IndexConfig(
            name="event_index",
            space=KnowledgeSpace.EVENT,
            collection_name="diplomatic_events",
            description="News, statements, and press releases",
            document_types=["news", "statement", "press_release", "announcement", "speech", "interview"],
            priority=2
        ),
        KnowledgeSpace.ECONOMIC: IndexConfig(
            name="economic_index",
            space=KnowledgeSpace.ECONOMIC,
            collection_name="diplomatic_economic",
            description="Trade data, sanctions, and economic indicators",
            document_types=["trade_data", "sanctions", "tariff", "statistics", "report"],
            priority=3
        ),
        KnowledgeSpace.STRATEGIC: IndexConfig(
            name="strategic_index",
            space=KnowledgeSpace.STRATEGIC,
            collection_name="diplomatic_strategic",
            description="Analysis and think tank reports",
            document_types=["analysis", "research", "report", "assessment", "brief"],
            priority=4
        ),
    }
    
    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or "data/knowledge_indexes"
        self._indexes: Dict[KnowledgeSpace, Any] = {}
        self._initialized = False
        self._vector_store = None
    
    def initialize(self):
        """Initialize all knowledge indexes."""
        if self._initialized:
            return
        
        print("[MultiIndex] Initializing knowledge indexes...")
        
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Wire to the real per-space VectorStore
        try:
            from .vector_store import get_vector_store
            self._vector_store = get_vector_store(self.data_dir)
        except Exception as exc:
            print(f"[MultiIndex] VectorStore unavailable: {exc}")
            self._vector_store = None
        
        for space, config in self.INDEX_CONFIGS.items():
            self._indexes[space] = {
                "config": config,
                "documents": [],  # in-memory backup
            }
            print(f"[MultiIndex] Initialized {config.name}")
        
        self._initialized = True
    
    def route_document(self, document: Dict) -> KnowledgeSpace:
        """
        Determine which knowledge space a document belongs to.
        
        Args:
            document: Document with metadata including 'type' field
            
        Returns:
            The appropriate KnowledgeSpace
        """
        doc_type = document.get("metadata", {}).get("type", "").lower()
        doc_source = document.get("metadata", {}).get("source", "").lower()
        content = document.get("content", "").lower()[:500]
        
        # Check document type against each space's accepted types
        for space, config in self.INDEX_CONFIGS.items():
            if doc_type in config.document_types:
                return space
        
        # Heuristic: check content keywords
        legal_keywords = ["treaty", "article", "provision", "ratified", "legally binding", "convention"]
        event_keywords = ["announced", "statement", "press release", "said", "reported", "according to"]
        economic_keywords = ["trade", "tariff", "sanction", "billion", "million", "percent", "gdp"]
        strategic_keywords = ["analysis", "assessment", "implications", "scenario", "strategic"]
        
        if any(kw in content for kw in legal_keywords):
            return KnowledgeSpace.LEGAL
        elif any(kw in content for kw in economic_keywords):
            return KnowledgeSpace.ECONOMIC
        elif any(kw in content for kw in strategic_keywords):
            return KnowledgeSpace.STRATEGIC
        elif any(kw in content for kw in event_keywords):
            return KnowledgeSpace.EVENT
        
        # Default to EVENT
        return KnowledgeSpace.EVENT
    
    def add_document(
        self, 
        document: Dict, 
        space: KnowledgeSpace = None
    ):
        """
        Add a document to the appropriate knowledge index.
        
        Args:
            document: Document to add
            space: Optional, specify space or auto-route
        """
        self.initialize()
        
        if space is None:
            space = self.route_document(document)
        
        if space not in self._indexes:
            print(f"[MultiIndex] Warning: Unknown space {space}, using EVENT")
            space = KnowledgeSpace.EVENT
        
        # Add to real vector store per-space collection
        if self._vector_store:
            try:
                chunk = {
                    "id":   document.get("id", str(hash(str(document)))),
                    "text": document.get("content", ""),
                    "metadata": document.get("metadata", {}),
                }
                self._vector_store.add_chunks(space.value, [chunk])
            except Exception as e:
                print(f"[MultiIndex] Error adding to vector store: {e}")
        
        # Also keep in memory for keyword fallback
        self._indexes[space]["documents"].append(document)
        
        print(f"[MultiIndex] Added document to {space.value} index")
    
    def add_documents(self, documents: List[Dict]):
        """Add multiple documents, auto-routing each."""
        for doc in documents:
            self.add_document(doc)
    
    def search(
        self,
        query: str,
        spaces: List[KnowledgeSpace] = None,
        top_k: int = 10,
        time_filter: Optional[tuple] = None,
        filters: Dict = None
    ) -> List[Dict]:
        """
        Search across specified knowledge spaces.
        
        Args:
            query: Search query
            spaces: Which spaces to search (None = all)
            top_k: Results per space
            time_filter: Optional (start_date, end_date) tuple
            filters: Additional metadata filters
            
        Returns:
            Combined results from all searched spaces
        """
        self.initialize()
        
        if spaces is None:
            spaces = list(KnowledgeSpace)
        
        all_results = []
        
        # Search each specified space
        for space in spaces:
            if space not in self._indexes:
                continue
            
            index_data = self._indexes[space]
            
            try:
                results = []
                if self._vector_store:
                    # Use real per-space vector search
                    results = self._vector_store.search(
                        query=query,
                        space=space.value,
                        top_k=top_k,
                    )
                
                if not results:
                    # Fallback: simple keyword search on in-memory docs
                    results = self._keyword_search(
                        query, 
                        index_data["documents"], 
                        top_k
                    )
                
                # Add space metadata to results
                for result in results:
                    result["_knowledge_space"] = space.value
                    result["_space_priority"] = index_data["config"].priority
                
                # Apply time filter if specified
                if time_filter:
                    results = self._apply_time_filter(results, time_filter)
                
                all_results.extend(results)
                
            except Exception as e:
                print(f"[MultiIndex] Error searching {space.value}: {e}")
        
        # Sort by relevance score if available
        all_results.sort(
            key=lambda x: x.get("score", 0),
            reverse=True
        )
        
        return all_results[:top_k]
    
    def _keyword_search(
        self, 
        query: str, 
        documents: List[Dict], 
        top_k: int
    ) -> List[Dict]:
        """Simple keyword search fallback."""
        query_words = set(query.lower().split())
        
        scored = []
        for doc in documents:
            content = doc.get("content", "").lower()
            content_words = set(content.split())
            
            # Score by word overlap
            overlap = len(query_words & content_words)
            score = overlap / len(query_words) if query_words else 0
            
            if score > 0:
                doc_copy = doc.copy()
                doc_copy["score"] = score
                scored.append(doc_copy)
        
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]
    
    def _apply_time_filter(
        self, 
        documents: List[Dict], 
        time_filter: tuple
    ) -> List[Dict]:
        """Filter documents by time range."""
        start_date, end_date = time_filter
        filtered = []
        
        for doc in documents:
            doc_date = doc.get("metadata", {}).get("date", "")
            
            if not doc_date:
                # No date, include by default
                filtered.append(doc)
            elif start_date <= doc_date <= end_date:
                filtered.append(doc)
        
        return filtered
    
    def get_space_stats(self) -> Dict[str, int]:
        """Get document counts per space."""
        self.initialize()
        
        if self._vector_store:
            return self._vector_store.get_stats()
        
        return {
            space.value: len(self._indexes.get(space, {}).get("documents", []))
            for space in KnowledgeSpace
        }
    
    def get_recommended_spaces(
        self, 
        query_type: str, 
        required_evidence: List[str]
    ) -> List[KnowledgeSpace]:
        """Get recommended spaces based on query analysis."""
        spaces = set()
        
        # Map query types to spaces
        type_mapping = {
            "legal": [KnowledgeSpace.LEGAL],
            "factual": [KnowledgeSpace.EVENT],
            "temporal": [KnowledgeSpace.EVENT, KnowledgeSpace.LEGAL],
            "comparative": [KnowledgeSpace.LEGAL, KnowledgeSpace.ECONOMIC],
            "causal": [KnowledgeSpace.EVENT, KnowledgeSpace.STRATEGIC],
            "predictive": [KnowledgeSpace.STRATEGIC],
            "procedural": [KnowledgeSpace.LEGAL],
        }
        
        if query_type in type_mapping:
            spaces.update(type_mapping[query_type])
        
        # Map evidence types to spaces
        evidence_mapping = {
            "treaty_text": KnowledgeSpace.LEGAL,
            "legal_provision": KnowledgeSpace.LEGAL,
            "official_statement": KnowledgeSpace.EVENT,
            "news_report": KnowledgeSpace.EVENT,
            "statistical_data": KnowledgeSpace.ECONOMIC,
            "historical_record": KnowledgeSpace.EVENT,
            "expert_analysis": KnowledgeSpace.STRATEGIC,
        }
        
        for evidence in required_evidence:
            if evidence in evidence_mapping:
                spaces.add(evidence_mapping[evidence])
        
        return list(spaces) if spaces else [KnowledgeSpace.EVENT]


# Singleton instance
multi_index_manager = MultiIndexManager()


__all__ = [
    "MultiIndexManager",
    "multi_index_manager",
    "KnowledgeSpace",
    "IndexConfig",
]
