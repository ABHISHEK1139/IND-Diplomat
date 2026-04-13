"""
Temporal Retriever - Time-Aware Retrieval System
==================================================
Filters documents by time BEFORE the model reads them.

Key Insight:
Diplomacy is 70% time-dependent.
"India-US relation" in 2005 ≠ 2024
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import re


class TemporalScope(Enum):
    """Types of temporal context."""
    CURRENT = "current"           # Right now, latest
    RECENT = "recent"             # Last 1-2 years
    SPECIFIC_YEAR = "specific"    # A particular year
    HISTORICAL = "historical"     # Long-term history
    TREND = "trend"               # Change over time
    FUTURE = "future"             # Predictions


@dataclass
class TemporalContext:
    """Detected temporal context from a query."""
    scope: TemporalScope
    start_date: Optional[str]
    end_date: Optional[str]
    specific_year: Optional[str]
    confidence: float
    reasoning: str
    requires_historical: bool = False


class TemporalRetriever:
    """
    Time-aware retrieval that filters documents by temporal relevance.
    
    Key Principle:
    Filter by time BEFORE the model reads documents,
    not after the answer is generated.
    
    Usage:
        temporal = TemporalRetriever()
        
        # Detect temporal context
        context = temporal.detect_temporal_context(
            "What is India's current policy on RCEP?"
        )
        
        # Filter documents
        filtered = temporal.apply_temporal_filter(documents, context)
    """
    
    def __init__(self):
        self._current_year = datetime.now().year
        
        # Temporal indicators
        self._current_indicators = [
            'current', 'now', 'today', 'present', 'existing',
            'latest', 'ongoing', 'active'
        ]
        
        self._recent_indicators = [
            'recent', 'recently', 'last year', 'past year',
            'this year', 'lately', 'just'
        ]
        
        self._historical_indicators = [
            'history', 'historical', 'evolution', 'origin',
            'began', 'started', 'founded', 'established'
        ]
        
        self._trend_indicators = [
            'over time', 'changed', 'evolved', 'trend',
            'progression', 'development'
        ]
        
        self._future_indicators = [
            'will', 'would', 'future', 'upcoming', 'planned',
            'expected', 'predicted'
        ]
    
    def detect_temporal_context(self, query: str) -> TemporalContext:
        """
        Detect time-related context in a query.
        
        Args:
            query: The user's question
            
        Returns:
            TemporalContext with detected time scope
        """
        query_lower = query.lower()
        
        # Check for specific year
        year_match = re.search(r'\b(19|20)\d{2}\b', query)
        if year_match:
            year = year_match.group()
            return TemporalContext(
                scope=TemporalScope.SPECIFIC_YEAR,
                start_date=f"{year}-01-01",
                end_date=f"{year}-12-31",
                specific_year=year,
                confidence=0.95,
                reasoning=f"Specific year mentioned: {year}"
            )
        
        # Check for date ranges
        range_match = re.search(
            r'\b(19|20)(\d{2})\s*[-–to]\s*(19|20)(\d{2})\b', 
            query
        )
        if range_match:
            start = f"{range_match.group(1)}{range_match.group(2)}"
            end = f"{range_match.group(3)}{range_match.group(4)}"
            return TemporalContext(
                scope=TemporalScope.TREND,
                start_date=f"{start}-01-01",
                end_date=f"{end}-12-31",
                specific_year=None,
                confidence=0.9,
                reasoning=f"Date range: {start} to {end}",
                requires_historical=True
            )
        
        # Check for temporal indicators
        if any(ind in query_lower for ind in self._current_indicators):
            return TemporalContext(
                scope=TemporalScope.CURRENT,
                start_date=f"{self._current_year - 1}-01-01",
                end_date=f"{self._current_year + 1}-12-31",
                specific_year=None,
                confidence=0.85,
                reasoning="Current/present indicators found"
            )
        
        if any(ind in query_lower for ind in self._recent_indicators):
            return TemporalContext(
                scope=TemporalScope.RECENT,
                start_date=f"{self._current_year - 2}-01-01",
                end_date=f"{self._current_year + 1}-12-31",
                specific_year=None,
                confidence=0.8,
                reasoning="Recent/last year indicators found"
            )
        
        if any(ind in query_lower for ind in self._trend_indicators):
            return TemporalContext(
                scope=TemporalScope.TREND,
                start_date=f"{self._current_year - 10}-01-01",
                end_date=f"{self._current_year + 1}-12-31",
                specific_year=None,
                confidence=0.75,
                reasoning="Trend/evolution indicators found",
                requires_historical=True
            )
        
        if any(ind in query_lower for ind in self._historical_indicators):
            return TemporalContext(
                scope=TemporalScope.HISTORICAL,
                start_date=None,  # No start limit
                end_date=f"{self._current_year + 1}-12-31",
                specific_year=None,
                confidence=0.7,
                reasoning="Historical indicators found",
                requires_historical=True
            )
        
        if any(ind in query_lower for ind in self._future_indicators):
            return TemporalContext(
                scope=TemporalScope.FUTURE,
                start_date=f"{self._current_year}-01-01",
                end_date=None,  # No end limit
                specific_year=None,
                confidence=0.7,
                reasoning="Future/prediction indicators found"
            )
        
        # Default: assume current context
        return TemporalContext(
            scope=TemporalScope.CURRENT,
            start_date=f"{self._current_year - 2}-01-01",
            end_date=f"{self._current_year + 1}-12-31",
            specific_year=None,
            confidence=0.5,
            reasoning="No explicit temporal context, assuming current"
        )
    
    def apply_temporal_filter(
        self, 
        documents: List[Dict], 
        context: TemporalContext
    ) -> List[Dict]:
        """
        Filter documents by temporal relevance.
        
        Args:
            documents: List of documents with date metadata
            context: Detected temporal context
            
        Returns:
            Filtered list of temporally relevant documents
        """
        if not context.start_date and not context.end_date:
            return documents  # No filtering needed
        
        filtered = []
        for doc in documents:
            doc_date = self._extract_document_date(doc)
            
            if doc_date is None:
                # No date = include by default for important legal docs
                doc_type = doc.get("metadata", {}).get("type", "")
                if doc_type in ["treaty", "law", "agreement"]:
                    filtered.append(doc)
                    continue
                # Skip undated dynamic content unless historical
                if context.requires_historical:
                    filtered.append(doc)
                continue
            
            # Check if document falls within range
            in_range = True
            
            if context.start_date and doc_date < context.start_date:
                in_range = False
            
            if context.end_date and doc_date > context.end_date:
                in_range = False
            
            if in_range:
                filtered.append(doc)
        
        print(f"[TemporalRetriever] Filtered {len(documents)} → {len(filtered)} docs")
        print(f"[TemporalRetriever] Scope: {context.scope.value}")
        
        return filtered
    
    def _extract_document_date(self, doc: Dict) -> Optional[str]:
        """Extract date string from document."""
        metadata = doc.get("metadata", {})
        
        # Check common date fields
        for field in ["date", "publication_date", "published", "created_at", "timestamp"]:
            if field in metadata:
                date_val = metadata[field]
                if isinstance(date_val, str):
                    # Normalize to YYYY-MM-DD format
                    return self._normalize_date(date_val)
        
        return None
    
    def _normalize_date(self, date_str: str) -> Optional[str]:
        """Normalize date string to YYYY-MM-DD format."""
        # Try common formats
        formats = [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%B %d, %Y",
            "%d %B %Y",
            "%Y"
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.strip()[:10], fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        
        # Try to extract just the year
        year_match = re.search(r'(19|20)\d{2}', date_str)
        if year_match:
            return f"{year_match.group()}-01-01"
        
        return None
    
    def enhance_query_with_temporal(
        self, 
        query: str, 
        context: TemporalContext
    ) -> str:
        """Enhance query with temporal context for better retrieval."""
        if context.scope == TemporalScope.SPECIFIC_YEAR:
            return f"{query} {context.specific_year}"
        
        if context.scope == TemporalScope.CURRENT:
            return f"{query} {self._current_year} current latest"
        
        if context.scope == TemporalScope.HISTORICAL:
            return f"{query} history origin evolution"
        
        if context.scope == TemporalScope.TREND:
            return f"{query} trend change evolution over years"
        
        return query
    
    def get_temporal_summary(self, context: TemporalContext) -> Dict[str, Any]:
        """Get summary of temporal context."""
        return {
            "scope": context.scope.value,
            "start_date": context.start_date,
            "end_date": context.end_date,
            "specific_year": context.specific_year,
            "confidence": context.confidence,
            "reasoning": context.reasoning,
            "requires_historical": context.requires_historical
        }


# Singleton instance
temporal_retriever = TemporalRetriever()


__all__ = [
    "TemporalRetriever",
    "temporal_retriever",
    "TemporalContext",
    "TemporalScope",
]
