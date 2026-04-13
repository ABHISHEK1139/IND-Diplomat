"""
Dynamic Temporal Memory - Timeline Integration for Neo4j
Implements DyG-RAG (Dynamic Graph RAG) with temporal validity intervals.
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import re


class TemporalStatus(Enum):
    """Temporal validity status."""
    ACTIVE = "active"           # Currently in force
    EXPIRED = "expired"         # Past validity period
    SUPERSEDED = "superseded"   # Replaced by newer version
    PENDING = "pending"         # Not yet effective
    SUSPENDED = "suspended"     # Temporarily inactive


@dataclass
class TemporalNode:
    """
    A node with temporal validity interval [t_start, t_end].
    Used for treaties, agreements, statements, etc.
    """
    node_id: str
    node_type: str
    title: str
    content: str
    
    # Temporal bounds
    t_start: datetime  # Effective date
    t_end: Optional[datetime]  # Expiry date (None = perpetual)
    
    # Validity
    status: TemporalStatus
    superseded_by: Optional[str]
    supersedes: Optional[str]
    
    # Metadata
    jurisdiction: str
    signatories: List[str]
    source: str
    
    def is_valid_at(self, timestamp: datetime) -> bool:
        """Check if node is valid at given timestamp."""
        if timestamp < self.t_start:
            return False
        if self.t_end and timestamp > self.t_end:
            return False
        if self.status in [TemporalStatus.EXPIRED, TemporalStatus.SUPERSEDED]:
            return False
        return True
    
    def temporal_relevance(self, reference: datetime) -> float:
        """Calculate temporal relevance score (0-1)."""
        if not self.is_valid_at(reference):
            return 0.0
        
        # Decay based on age
        age_days = (reference - self.t_start).days
        
        if age_days < 365:  # < 1 year old
            return 1.0
        elif age_days < 365 * 5:  # 1-5 years
            return 0.8
        elif age_days < 365 * 10:  # 5-10 years
            return 0.6
        else:
            return 0.4


class TemporalGraphManager:
    """
    Manages temporal reasoning over the knowledge graph.
    Implements DyG-RAG (Dynamic Graph RAG) patterns.
    """
    
    def __init__(self, neo4j_driver=None):
        self.driver = neo4j_driver
        self._temporal_index: Dict[str, TemporalNode] = {}
        self._supersession_chains: Dict[str, List[str]] = {}
    
    def register_temporal_node(self, node: TemporalNode) -> str:
        """Register a node with temporal metadata."""
        self._temporal_index[node.node_id] = node
        
        # Track supersession
        if node.supersedes:
            if node.supersedes in self._temporal_index:
                old_node = self._temporal_index[node.supersedes]
                old_node.status = TemporalStatus.SUPERSEDED
                old_node.superseded_by = node.node_id
            
            # Build chain
            chain = self._supersession_chains.get(node.supersedes, [node.supersedes])
            chain.append(node.node_id)
            self._supersession_chains[node.node_id] = chain
        
        return node.node_id
    
    def time_aware_query(
        self,
        query: str,
        as_of_date: datetime = None,
        include_historical: bool = False
    ) -> Tuple[str, List[TemporalNode]]:
        """
        Enhance query with temporal awareness.
        Returns enhanced query and relevant temporal nodes.
        """
        if as_of_date is None:
            as_of_date = datetime.now()
        
        # Detect temporal intent in query
        temporal_keywords = {
            "current": 0,
            "now": 0,
            "currently": 0,
            "today": 0,
            "historical": -1,
            "history": -1,
            "was": -1,
            "were": -1,
            "original": -1,
            "future": 1,
            "upcoming": 1,
            "proposed": 1
        }
        
        temporal_direction = 0  # -1 = past, 0 = present, 1 = future
        for word, direction in temporal_keywords.items():
            if word in query.lower():
                temporal_direction = direction
                break
        
        # Filter nodes by temporal validity
        valid_nodes = []
        for node in self._temporal_index.values():
            if include_historical or node.is_valid_at(as_of_date):
                valid_nodes.append(node)
        
        # Sort by temporal relevance
        valid_nodes.sort(key=lambda n: n.temporal_relevance(as_of_date), reverse=True)
        
        # Enhance query
        if temporal_direction == 0:
            enhanced = f"[As of {as_of_date.strftime('%Y-%m-%d')}] {query}"
        elif temporal_direction == -1:
            enhanced = f"[Historical context] {query}"
        else:
            enhanced = f"[Future/Proposed] {query}"
        
        return enhanced, valid_nodes
    
    def get_current_version(self, node_id: str) -> Optional[TemporalNode]:
        """Get the current (non-superseded) version of a document."""
        node = self._temporal_index.get(node_id)
        
        if not node:
            return None
        
        # Follow supersession chain to latest
        current = node
        while current.superseded_by:
            if current.superseded_by in self._temporal_index:
                current = self._temporal_index[current.superseded_by]
            else:
                break
        
        return current
    
    def get_version_history(self, node_id: str) -> List[TemporalNode]:
        """Get full version history of a document."""
        # Find the root
        node = self._temporal_index.get(node_id)
        if not node:
            return []
        
        # Go back to original
        root = node
        while root.supersedes and root.supersedes in self._temporal_index:
            root = self._temporal_index[root.supersedes]
        
        # Build forward chain
        history = [root]
        current = root
        while current.superseded_by and current.superseded_by in self._temporal_index:
            current = self._temporal_index[current.superseded_by]
            history.append(current)
        
        return history
    
    def detect_temporal_conflicts(
        self,
        sources: List[Dict],
        as_of_date: datetime = None
    ) -> List[Dict[str, Any]]:
        """
        Detect temporal conflicts in retrieved sources.
        E.g., mixing current and superseded versions.
        """
        if as_of_date is None:
            as_of_date = datetime.now()
        
        conflicts = []
        dated_sources = []
        
        for i, src in enumerate(sources):
            # Extract date from source
            date = self._extract_date(src)
            if date:
                dated_sources.append((i, date, src))
        
        # Check for issues
        for i, (idx1, date1, src1) in enumerate(dated_sources):
            for idx2, date2, src2 in dated_sources[i+1:]:
                year_diff = abs(date1.year - date2.year)
                
                # Flag significant temporal gaps
                if year_diff > 10:
                    conflicts.append({
                        "type": "large_temporal_gap",
                        "source1_idx": idx1,
                        "source2_idx": idx2,
                        "date1": date1.isoformat(),
                        "date2": date2.isoformat(),
                        "gap_years": year_diff,
                        "warning": f"Sources are {year_diff} years apart. Older source may be superseded."
                    })
                
                # Check if one might supersede the other
                if self._might_be_superseded(src1, src2):
                    conflicts.append({
                        "type": "possible_supersession",
                        "older_source_idx": idx1 if date1 < date2 else idx2,
                        "newer_source_idx": idx2 if date1 < date2 else idx1,
                        "warning": "Newer version may supersede older document"
                    })
        
        return conflicts
    
    def _extract_date(self, source: Dict) -> Optional[datetime]:
        """Extract date from source metadata or content."""
        # Check metadata first
        meta = source.get("metadata", {})
        
        for key in ["date", "effective_date", "signed_date", "published"]:
            if key in meta:
                return self._parse_date(str(meta[key]))
        
        # Try content
        content = source.get("content", "")[:500]
        patterns = [
            r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})",
            r"(\d{4})-(\d{2})-(\d{2})"
        ]
        
        month_map = {
            "january": 1, "february": 2, "march": 3, "april": 4,
            "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12
        }
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                groups = match.groups()
                try:
                    if len(groups) == 3:
                        if groups[1].lower() in month_map:
                            return datetime(int(groups[2]), month_map[groups[1].lower()], int(groups[0]))
                        else:
                            return datetime(int(groups[0]), int(groups[1]), int(groups[2]))
                except:
                    continue
        
        return None
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse various date formats."""
        formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%Y",
            "%B %d, %Y",
            "%d %B %Y"
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except:
                continue
        
        # Try year only
        year_match = re.search(r"(\d{4})", date_str)
        if year_match:
            try:
                return datetime(int(year_match.group(1)), 1, 1)
            except:
                pass
        
        return None
    
    def _might_be_superseded(self, src1: Dict, src2: Dict) -> bool:
        """Check if documents might be in a supersession relationship."""
        content1 = src1.get("content", "").lower()
        content2 = src2.get("content", "").lower()
        
        # Check for amendment/revision indicators
        supersession_markers = [
            "amends", "replaces", "supersedes", "revision",
            "updated", "modified", "amended"
        ]
        
        return any(marker in content1 or marker in content2 for marker in supersession_markers)
    
    def generate_temporal_context(
        self,
        sources: List[Dict],
        as_of_date: datetime = None
    ) -> str:
        """Generate temporal context summary for the model."""
        if as_of_date is None:
            as_of_date = datetime.now()
        
        conflicts = self.detect_temporal_conflicts(sources, as_of_date)
        
        context_parts = [
            f"**Temporal Context** (as of {as_of_date.strftime('%Y-%m-%d')})",
            f"- Sources span from: [dates extracted from {len(sources)} documents]"
        ]
        
        if conflicts:
            context_parts.append(f"- ⚠️ {len(conflicts)} temporal conflict(s) detected:")
            for c in conflicts[:3]:
                context_parts.append(f"  - {c.get('warning', 'Temporal issue detected')}")
        else:
            context_parts.append("- ✅ No temporal conflicts detected")
        
        return "\n".join(context_parts)
    
    # Neo4j Cypher Query Helpers
    
    def cypher_time_filter(self, as_of_date: datetime = None) -> str:
        """Generate Cypher WHERE clause for temporal filtering."""
        if as_of_date is None:
            as_of_date = datetime.now()
        
        date_str = as_of_date.strftime("%Y-%m-%d")
        
        return f"""
        WHERE n.t_start <= date("{date_str}")
        AND (n.t_end IS NULL OR n.t_end >= date("{date_str}"))
        AND n.status <> 'superseded'
        """
    
    def cypher_version_traversal(self, node_id: str) -> str:
        """Generate Cypher query to traverse version chain."""
        return f"""
        MATCH path = (root)-[:SUPERSEDES*0..]->(current)
        WHERE root.id = "{node_id}" OR current.id = "{node_id}"
        RETURN nodes(path) as versions
        ORDER BY length(path) DESC
        LIMIT 1
        """


    def add_temporal_context(
        self,
        documents: List[Dict],
        query: str,
        as_of_date: datetime = None
    ) -> List[Dict]:
        """
        Add temporal context to documents for pipeline integration.
        Filters and enriches documents with temporal metadata.
        """
        if as_of_date is None:
            as_of_date = datetime.now()
        
        enriched = []
        
        for doc in documents:
            doc_copy = doc.copy()
            
            # Extract date from document
            doc_date = self._extract_date(doc)
            
            if doc_date:
                # Calculate temporal relevance
                age_days = (as_of_date - doc_date).days
                
                if age_days < 365:
                    relevance = 1.0
                elif age_days < 365 * 5:
                    relevance = 0.8
                elif age_days < 365 * 10:
                    relevance = 0.6
                else:
                    relevance = 0.4
                
                doc_copy["temporal_relevance"] = relevance
                doc_copy["document_date"] = doc_date.isoformat()
                doc_copy["age_days"] = age_days
            else:
                doc_copy["temporal_relevance"] = 0.5  # Unknown date
            
            enriched.append(doc_copy)
        
        # Sort by temporal relevance
        enriched.sort(key=lambda d: d.get("temporal_relevance", 0.5), reverse=True)
        
        return enriched


# Singleton instance
temporal_graph = TemporalGraphManager()
