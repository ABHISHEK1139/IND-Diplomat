"""
Timeline Manager - Dynamic Event Units (DEU)

Timeline/version state now lives in Layer3_StateModel so reasoning can consume
state snapshots without owning mutation logic.
"""

import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class TemporalRelation(Enum):
    """Temporal relations between events/documents."""
    BEFORE = "before"
    AFTER = "after"
    DURING = "during"
    OVERLAPS = "overlaps"
    SUPERSEDES = "supersedes"
    AMENDS = "amends"
    EXPIRES = "expires"
    RENEWS = "renews"


@dataclass
class DynamicEventUnit:
    """
    Dynamic Event Unit (DEU) - temporal unit for diplomatic events.
    Tracks validity periods, supersession chains, and temporal context.
    """
    event_id: str
    event_type: str  # treaty, amendment, statement, sanction, etc.
    title: str
    content: str
    
    # Temporal bounds
    effective_date: datetime
    expiry_date: Optional[datetime]
    
    # Validity
    is_active: bool
    superseded_by: Optional[str]  # ID of superseding event
    supersedes: Optional[str]  # ID of event this supersedes
    
    # Context
    jurisdiction: str
    signatories: List[str]
    metadata: Dict[str, Any]
    
    def is_valid_at(self, check_date: datetime) -> bool:
        """Check if event is valid at a specific date."""
        if check_date < self.effective_date:
            return False
        if self.expiry_date and check_date > self.expiry_date:
            return False
        if self.superseded_by:
            return False
        return self.is_active
    
    def temporal_distance(self, from_date: datetime) -> timedelta:
        """Calculate temporal distance from a reference date."""
        return abs(from_date - self.effective_date)


class TimelineManager:
    """
    Manages temporal reasoning and time-aware traversal of knowledge.
    Ensures the model doesn't cite expired laws as current fact.
    """
    
    def __init__(self):
        self._events: Dict[str, DynamicEventUnit] = {}
        self._supersession_chains: Dict[str, List[str]] = {}
        self._temporal_index: Dict[str, List[str]] = {}  # year -> event_ids
        
        # Date patterns for extraction
        self._date_patterns = [
            r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})",
            r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})",
            r"(\d{4})-(\d{2})-(\d{2})",
            r"(\d{2})/(\d{2})/(\d{4})",
        ]
        
        self._month_map = {
            "january": 1, "february": 2, "march": 3, "april": 4,
            "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12
        }
    
    def register_event(self, deu: DynamicEventUnit) -> str:
        """Register a Dynamic Event Unit."""
        self._events[deu.event_id] = deu
        
        # Index by year
        year = str(deu.effective_date.year)
        if year not in self._temporal_index:
            self._temporal_index[year] = []
        self._temporal_index[year].append(deu.event_id)
        
        # Track supersession
        if deu.supersedes:
            self._supersession_chains[deu.supersedes] = self._supersession_chains.get(deu.supersedes, [])
            self._supersession_chains[deu.supersedes].append(deu.event_id)
            
            # Mark superseded event
            if deu.supersedes in self._events:
                self._events[deu.supersedes].superseded_by = deu.event_id
                self._events[deu.supersedes].is_active = False
        
        return deu.event_id
    
    def extract_date_from_text(self, text: str) -> Optional[datetime]:
        """Extract date from natural language text."""
        for pattern in self._date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                
                try:
                    if len(groups) == 3:
                        if groups[1].lower() in self._month_map:
                            # Day Month Year
                            day = int(groups[0])
                            month = self._month_map[groups[1].lower()]
                            year = int(groups[2])
                        elif groups[0].lower() in self._month_map:
                            # Month Day Year
                            month = self._month_map[groups[0].lower()]
                            day = int(groups[1])
                            year = int(groups[2])
                        else:
                            # ISO or numeric format
                            if int(groups[0]) > 31:  # Year first
                                year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                            else:  # Day first
                                day, month, year = int(groups[0]), int(groups[1]), int(groups[2])
                        
                        return datetime(year, month, day)
                except:
                    continue
        
        return None
    
    def get_temporal_relation(
        self, 
        event1: DynamicEventUnit, 
        event2: DynamicEventUnit
    ) -> TemporalRelation:
        """Determine temporal relation between two events."""
        if event1.supersedes == event2.event_id:
            return TemporalRelation.SUPERSEDES
        if event2.supersedes == event1.event_id:
            return TemporalRelation.SUPERSEDES
        
        if event1.effective_date < event2.effective_date:
            if event1.expiry_date and event1.expiry_date > event2.effective_date:
                return TemporalRelation.OVERLAPS
            return TemporalRelation.BEFORE
        elif event1.effective_date > event2.effective_date:
            return TemporalRelation.AFTER
        else:
            return TemporalRelation.DURING
    
    def time_aware_traversal(
        self,
        query_date: datetime,
        jurisdiction: str = None,
        event_type: str = None,
        include_expired: bool = False
    ) -> List[DynamicEventUnit]:
        """
        Perform time-aware traversal of events.
        Returns only events valid at the query date.
        """
        results = []
        
        for event in self._events.values():
            # Filter by jurisdiction
            if jurisdiction and event.jurisdiction != jurisdiction:
                continue
            
            # Filter by event type
            if event_type and event.event_type != event_type:
                continue
            
            # Check temporal validity
            if include_expired or event.is_valid_at(query_date):
                results.append(event)
        
        # Sort by temporal relevance (closest to query date first)
        results.sort(key=lambda e: e.temporal_distance(query_date))
        
        return results
    
    def get_current_state(
        self, 
        topic: str, 
        as_of_date: datetime = None
    ) -> Dict[str, Any]:
        """
        Get the current legal/diplomatic state of a topic as of a date.
        Follows supersession chains to find the latest valid version.
        """
        if as_of_date is None:
            as_of_date = datetime.now()
        
        # Find relevant events
        relevant = []
        for event in self._events.values():
            if topic.lower() in event.title.lower() or topic.lower() in event.content.lower():
                relevant.append(event)
        
        if not relevant:
            return {"found": False, "message": "No events found for topic"}
        
        # Find the most current valid version
        current = None
        history = []
        
        for event in sorted(relevant, key=lambda e: e.effective_date, reverse=True):
            if event.is_valid_at(as_of_date):
                current = event
                break
            else:
                history.append({
                    "event_id": event.event_id,
                    "title": event.title,
                    "effective_date": event.effective_date.isoformat(),
                    "status": "superseded" if event.superseded_by else "expired"
                })
        
        return {
            "found": current is not None,
            "current": {
                "event_id": current.event_id,
                "title": current.title,
                "effective_date": current.effective_date.isoformat(),
                "content": current.content[:500],
                "signatories": current.signatories
            } if current else None,
            "history": history,
            "as_of_date": as_of_date.isoformat()
        }
    
    def detect_temporal_conflicts(
        self, 
        sources: List[Dict]
    ) -> List[Dict[str, Any]]:
        """
        Detect temporal conflicts in retrieved sources.
        E.g., mixing a 1990 treaty with a 2024 amendment.
        """
        conflicts = []
        dated_sources = []
        
        # Extract dates from sources
        for i, src in enumerate(sources):
            date = None
            
            # Check metadata first
            if "date" in src.get("metadata", {}):
                date = self.extract_date_from_text(str(src["metadata"]["date"]))
            
            # Try content
            if not date:
                date = self.extract_date_from_text(src.get("content", "")[:500])
            
            if date:
                dated_sources.append((i, date, src))
        
        # Find conflicts (sources from different decades discussing same topic)
        for i, (idx1, date1, src1) in enumerate(dated_sources):
            for idx2, date2, src2 in dated_sources[i+1:]:
                year_diff = abs(date1.year - date2.year)
                
                if year_diff > 10:  # More than 10 years apart
                    conflicts.append({
                        "type": "temporal_gap",
                        "source1": {"index": idx1, "date": date1.isoformat()},
                        "source2": {"index": idx2, "date": date2.isoformat()},
                        "gap_years": year_diff,
                        "warning": f"Sources are {year_diff} years apart - verify current validity"
                    })
        
        return conflicts
    
    def add_temporal_context(
        self, 
        query: str, 
        sources: List[Dict]
    ) -> Tuple[str, List[Dict]]:
        """
        Enhance query and sources with temporal context.
        Returns enhanced query and sources with temporal annotations.
        """
        current_date = datetime.now()
        
        # Detect if query has temporal aspect
        temporal_keywords = ["current", "latest", "now", "today", "recent", "valid", "in force"]
        has_temporal = any(kw in query.lower() for kw in temporal_keywords)
        
        # Enhance query
        if has_temporal:
            enhanced_query = f"[As of {current_date.strftime('%Y-%m-%d')}] {query}"
        else:
            enhanced_query = query
        
        # Annotate sources with temporal status
        enhanced_sources = []
        for src in sources:
            src_date = None
            
            if "date" in src.get("metadata", {}):
                src_date = self.extract_date_from_text(str(src["metadata"]["date"]))
            
            temporal_status = "unknown"
            if src_date:
                years_old = (current_date - src_date).days / 365
                if years_old < 1:
                    temporal_status = "current"
                elif years_old < 5:
                    temporal_status = "recent"
                elif years_old < 10:
                    temporal_status = "dated"
                else:
                    temporal_status = "historical"
            
            enhanced_src = {
                **src,
                "temporal_status": temporal_status,
                "source_date": src_date.isoformat() if src_date else None,
                "temporal_warning": f"Source is {temporal_status}" if temporal_status in ["dated", "historical"] else None
            }
            enhanced_sources.append(enhanced_src)
        
        return enhanced_query, enhanced_sources


# Singleton instance
timeline_manager = TimelineManager()
