"""
EngramStore for IND-Diplomat
Advanced memory storage with datetime parsing, metadata-aware search, and thread safety.
"""

import os
import json
import hashlib
import threading
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass, field, asdict
from pathlib import Path

try:
    from rapidfuzz import fuzz, process
    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False
    print("[EngramStore] Warning: rapidfuzz not installed. Fuzzy matching disabled.")


@dataclass
class Engram:
    """Represents a stored memory unit."""
    id: str
    fingerprint: str
    content: str
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    version: int = 1
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d['created_at'] = self.created_at.isoformat()
        d['updated_at'] = self.updated_at.isoformat()
        return d
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Engram':
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        return cls(**data)


class EngramStore:
    """
    Production-grade Engram storage with:
    1. Datetime parsing for date range queries (not lexicographic)
    2. Metadata-aware search (page, jurisdiction, component_id)
    3. Fuzzy matching for clause variants
    4. Update/delete with collision handling
    5. Thread-safe operations
    """
    
    def __init__(self, persist_path: str = None):
        self.persist_path = Path(persist_path) if persist_path else Path("./data/engrams")
        self.persist_path.mkdir(parents=True, exist_ok=True)
        
        self._lock = threading.RLock()  # Reentrant lock for thread safety
        self._engrams: Dict[str, Engram] = {}
        self._fingerprint_index: Dict[str, str] = {}  # fingerprint -> id
        
        # Metadata indices for fast lookup
        self._metadata_indices: Dict[str, Dict[Any, List[str]]] = {
            "page": {},
            "jurisdiction": {},
            "component_id": {},
            "document_type": {}
        }
        
        self._load_from_disk()
    
    def _compute_fingerprint(self, content: str) -> str:
        """Computes content fingerprint for deduplication."""
        normalized = content.strip().lower()
        return hashlib.sha256(normalized.encode()).hexdigest()[:32]
    
    def _parse_date(self, date_value: Union[str, datetime, date]) -> datetime:
        """
        Parses date from various formats.
        Uses proper datetime comparison, not lexicographic string comparison.
        """
        if isinstance(date_value, datetime):
            return date_value
        if isinstance(date_value, date):
            return datetime.combine(date_value, datetime.min.time())
        
        # Try multiple formats
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%m/%d/%Y"
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_value, fmt)
            except ValueError:
                continue
        
        raise ValueError(f"Cannot parse date: {date_value}")
    
    def _update_indices(self, engram: Engram, remove: bool = False):
        """Updates metadata indices."""
        for key in self._metadata_indices:
            value = engram.metadata.get(key)
            if value is not None:
                if remove:
                    if value in self._metadata_indices[key]:
                        self._metadata_indices[key][value] = [
                            eid for eid in self._metadata_indices[key][value]
                            if eid != engram.id
                        ]
                else:
                    if value not in self._metadata_indices[key]:
                        self._metadata_indices[key][value] = []
                    if engram.id not in self._metadata_indices[key][value]:
                        self._metadata_indices[key][value].append(engram.id)
    
    # ============== CRUD Operations ==============
    
    def add(self, content: str, metadata: Dict[str, Any] = None, 
            embedding: List[float] = None, id: str = None) -> Tuple[str, bool]:
        """
        Adds or updates an engram.
        Returns: (id, is_new) - is_new=False means collision was handled
        """
        with self._lock:
            fingerprint = self._compute_fingerprint(content)
            metadata = metadata or {}
            
            # Check for collision
            existing_id = self._fingerprint_index.get(fingerprint)
            
            if existing_id:
                # Collision: update existing engram with new metadata
                existing = self._engrams[existing_id]
                existing.metadata.update(metadata)
                existing.updated_at = datetime.utcnow()
                existing.version += 1
                if embedding:
                    existing.embedding = embedding
                
                self._update_indices(existing)
                self._persist_engram(existing)
                return existing_id, False
            
            # New engram
            engram_id = id or f"engram_{len(self._engrams)}_{fingerprint[:8]}"
            engram = Engram(
                id=engram_id,
                fingerprint=fingerprint,
                content=content,
                embedding=embedding,
                metadata=metadata
            )
            
            self._engrams[engram_id] = engram
            self._fingerprint_index[fingerprint] = engram_id
            self._update_indices(engram)
            self._persist_engram(engram)
            
            return engram_id, True
    
    def get(self, engram_id: str) -> Optional[Engram]:
        """Gets an engram by ID."""
        with self._lock:
            return self._engrams.get(engram_id)
    
    def update(self, engram_id: str, content: str = None, 
               metadata: Dict[str, Any] = None) -> bool:
        """Updates an existing engram."""
        with self._lock:
            engram = self._engrams.get(engram_id)
            if not engram:
                return False
            
            if content:
                self._update_indices(engram, remove=True)
                old_fp = engram.fingerprint
                del self._fingerprint_index[old_fp]
                
                engram.content = content
                engram.fingerprint = self._compute_fingerprint(content)
                self._fingerprint_index[engram.fingerprint] = engram_id
            
            if metadata:
                engram.metadata.update(metadata)
            
            engram.updated_at = datetime.utcnow()
            engram.version += 1
            
            self._update_indices(engram)
            self._persist_engram(engram)
            return True
    
    def delete(self, engram_id: str) -> bool:
        """Deletes an engram."""
        with self._lock:
            engram = self._engrams.get(engram_id)
            if not engram:
                return False
            
            self._update_indices(engram, remove=True)
            del self._fingerprint_index[engram.fingerprint]
            del self._engrams[engram_id]
            
            # Remove from disk
            file_path = self.persist_path / f"{engram_id}.json"
            if file_path.exists():
                file_path.unlink()
            
            return True
    
    # ============== Search Operations ==============
    
    def search_by_date_range(
        self, 
        start_date: Union[str, datetime, date], 
        end_date: Union[str, datetime, date],
        date_field: str = "date"
    ) -> List[Engram]:
        """
        Searches engrams within a date range using proper datetime comparison.
        Avoids off-by-one errors from lexicographic string comparison.
        """
        with self._lock:
            start = self._parse_date(start_date)
            end = self._parse_date(end_date)
            
            results = []
            for engram in self._engrams.values():
                date_value = engram.metadata.get(date_field)
                if date_value:
                    try:
                        engram_date = self._parse_date(date_value)
                        # Proper datetime comparison (not string!)
                        if start <= engram_date <= end:
                            results.append(engram)
                    except ValueError:
                        continue
            
            return sorted(results, key=lambda e: self._parse_date(e.metadata.get(date_field, "1970-01-01")))
    
    def search_by_metadata(
        self,
        page: Optional[int] = None,
        jurisdiction: Optional[str] = None,
        component_id: Optional[str] = None,
        document_type: Optional[str] = None,
        **kwargs
    ) -> List[Engram]:
        """
        Metadata-aware search supporting page, jurisdiction, component_id.
        Uses indexed lookups for fast retrieval.
        """
        with self._lock:
            candidate_ids = None
            
            # Use indices for fast lookup
            filters = {
                "page": page,
                "jurisdiction": jurisdiction,
                "component_id": component_id,
                "document_type": document_type
            }
            filters.update(kwargs)
            
            for key, value in filters.items():
                if value is None:
                    continue
                
                if key in self._metadata_indices:
                    matching_ids = set(self._metadata_indices[key].get(value, []))
                else:
                    # Fallback to full scan for non-indexed fields
                    matching_ids = {
                        e.id for e in self._engrams.values()
                        if e.metadata.get(key) == value
                    }
                
                if candidate_ids is None:
                    candidate_ids = matching_ids
                else:
                    candidate_ids &= matching_ids
            
            if candidate_ids is None:
                return list(self._engrams.values())
            
            return [self._engrams[eid] for eid in candidate_ids if eid in self._engrams]
    
    def fuzzy_search(
        self, 
        query: str, 
        threshold: int = 70,
        limit: int = 10
    ) -> List[Tuple[Engram, float]]:
        """
        Fuzzy matching for clause variants using Levenshtein distance.
        Returns list of (engram, score) tuples.
        """
        if not FUZZY_AVAILABLE:
            # Fallback to simple substring matching
            results = []
            query_lower = query.lower()
            for engram in self._engrams.values():
                if query_lower in engram.content.lower():
                    results.append((engram, 100.0))
            return results[:limit]
        
        with self._lock:
            contents = [(e.id, e.content) for e in self._engrams.values()]
            
            if not contents:
                return []
            
            # Use rapidfuzz for fuzzy matching
            matches = process.extract(
                query,
                {eid: content for eid, content in contents},
                scorer=fuzz.partial_ratio,
                limit=limit,
                score_cutoff=threshold
            )
            
            results = []
            for match in matches:
                if len(match) >= 2:
                    engram_id = match[2] if len(match) > 2 else match[0]
                    score = match[1]
                    engram = self._engrams.get(engram_id)
                    if engram:
                        results.append((engram, score))
            
            return results
    
    def search_clauses(
        self,
        query: str,
        jurisdiction: str = None,
        date_range: Tuple[str, str] = None,
        fuzzy: bool = True,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Combined search with filtering and fuzzy matching.
        """
        with self._lock:
            # Start with all engrams or filtered by jurisdiction
            if jurisdiction:
                candidates = self.search_by_metadata(jurisdiction=jurisdiction)
            else:
                candidates = list(self._engrams.values())
            
            # Apply date range filter
            if date_range:
                start, end = date_range
                start_dt = self._parse_date(start)
                end_dt = self._parse_date(end)
                
                candidates = [
                    e for e in candidates
                    if e.metadata.get("date") and 
                    start_dt <= self._parse_date(e.metadata["date"]) <= end_dt
                ]
            
            # Apply fuzzy matching
            if fuzzy and FUZZY_AVAILABLE:
                contents = {e.id: e.content for e in candidates}
                if contents:
                    matches = process.extract(
                        query, contents,
                        scorer=fuzz.partial_ratio,
                        limit=limit
                    )
                    results = []
                    for match in matches:
                        engram_id = match[2] if len(match) > 2 else match[0]
                        engram = self._engrams.get(engram_id)
                        if engram:
                            results.append({
                                "engram": engram.to_dict(),
                                "score": match[1],
                                "match_type": "fuzzy"
                            })
                    return results
            
            # Fallback: simple keyword match
            query_lower = query.lower()
            results = []
            for e in candidates[:limit]:
                if query_lower in e.content.lower():
                    results.append({
                        "engram": e.to_dict(),
                        "score": 100.0,
                        "match_type": "keyword"
                    })
            
            return results
    
    # ============== Persistence ==============
    
    def _persist_engram(self, engram: Engram):
        """Persists single engram to disk."""
        file_path = self.persist_path / f"{engram.id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(engram.to_dict(), f, indent=2)
    
    def _load_from_disk(self):
        """Loads all engrams from disk."""
        if not self.persist_path.exists():
            return
        
        for file_path in self.persist_path.glob("*.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    engram = Engram.from_dict(data)
                    self._engrams[engram.id] = engram
                    self._fingerprint_index[engram.fingerprint] = engram.id
                    self._update_indices(engram)
            except Exception as e:
                print(f"[EngramStore] Error loading {file_path}: {e}")
    
    def persist_all(self):
        """Persists all engrams to disk."""
        with self._lock:
            for engram in self._engrams.values():
                self._persist_engram(engram)
    
    def stats(self) -> Dict[str, Any]:
        """Returns store statistics."""
        with self._lock:
            return {
                "total_engrams": len(self._engrams),
                "jurisdictions": list(self._metadata_indices["jurisdiction"].keys()),
                "components": list(self._metadata_indices["component_id"].keys()),
                "persist_path": str(self.persist_path)
            }


# Singleton instance
engram_store = EngramStore()
