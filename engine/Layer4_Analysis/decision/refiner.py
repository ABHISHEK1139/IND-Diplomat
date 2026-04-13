"""
Conflict Resolution & Refiner Agent
Detects inter-document conflicts and surfaces them as "Conflict Pairs".
"""

from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import re


class ConflictType(Enum):
    """Types of document conflicts."""
    FACTUAL = "factual"           # Different facts stated
    TEMPORAL = "temporal"         # Time-based inconsistency
    POSITIONAL = "positional"     # Different policy positions
    NUMERICAL = "numerical"       # Different numbers/statistics
    ATTRIBUTION = "attribution"   # Different attributed sources
    LEGAL = "legal"               # Legal interpretation differences


@dataclass
class ConflictPair:
    """A pair of conflicting statements."""
    conflict_id: str
    conflict_type: ConflictType
    source1: Dict[str, Any]  # {index, content, metadata}
    source2: Dict[str, Any]
    description: str
    severity: str  # "minor", "moderate", "major"
    resolution_suggestion: Optional[str]


@dataclass
class RefinementResult:
    """Result of refining sources for conflicts."""
    original_sources: int
    conflicts_detected: int
    conflict_pairs: List[ConflictPair]
    refined_answer: Optional[str]
    user_notes: List[str]
    trust_scores: Dict[int, float]  # source_index -> trust score


class RefinerAgent:
    """
    Detects and resolves inter-document conflicts.
    Surfaces conflicts to user when resolution isn't possible.
    """
    
    def __init__(self):
        # Conflict detection patterns
        self._negation_patterns = [
            (r"(\w+)\s+(?:is|are|was|were)\s+not\b", r"\1\s+(?:is|are|was|were)\b"),
            (r"never\s+(\w+)", r"always\s+\1"),
            (r"denied\s+(\w+)", r"confirmed\s+\1"),
            (r"rejected\s+(\w+)", r"accepted\s+\1"),
        ]
        
        # Numerical extraction pattern
        self._number_pattern = r"(\d+(?:\.\d+)?)\s*(%|percent|million|billion|trillion)?"
        
        # Date extraction pattern
        self._date_pattern = r"(\d{4}|\d{1,2}/\d{1,2}/\d{4}|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})"
    
    def detect_conflicts(self, sources: List[Dict]) -> List[ConflictPair]:
        """Detect conflicts across source documents."""
        conflicts = []
        conflict_id = 0
        
        for i, src1 in enumerate(sources):
            content1 = src1.get("content", "")
            
            for j, src2 in enumerate(sources[i+1:], start=i+1):
                content2 = src2.get("content", "")
                
                # Check for factual conflicts
                factual = self._detect_factual_conflict(content1, content2)
                if factual:
                    conflicts.append(ConflictPair(
                        conflict_id=f"conflict_{conflict_id}",
                        conflict_type=ConflictType.FACTUAL,
                        source1={"index": i, "content": content1[:300], "metadata": src1.get("metadata", {})},
                        source2={"index": j, "content": content2[:300], "metadata": src2.get("metadata", {})},
                        description=factual,
                        severity="moderate",
                        resolution_suggestion="Verify with primary source documents"
                    ))
                    conflict_id += 1
                
                # Check for numerical conflicts
                numerical = self._detect_numerical_conflict(content1, content2)
                if numerical:
                    conflicts.append(ConflictPair(
                        conflict_id=f"conflict_{conflict_id}",
                        conflict_type=ConflictType.NUMERICAL,
                        source1={"index": i, "content": content1[:300], "metadata": src1.get("metadata", {})},
                        source2={"index": j, "content": content2[:300], "metadata": src2.get("metadata", {})},
                        description=numerical,
                        severity="minor",
                        resolution_suggestion="Check source dates for most recent figures"
                    ))
                    conflict_id += 1
                
                # Check for temporal conflicts
                temporal = self._detect_temporal_conflict(src1, src2)
                if temporal:
                    conflicts.append(ConflictPair(
                        conflict_id=f"conflict_{conflict_id}",
                        conflict_type=ConflictType.TEMPORAL,
                        source1={"index": i, "content": content1[:300], "metadata": src1.get("metadata", {})},
                        source2={"index": j, "content": content2[:300], "metadata": src2.get("metadata", {})},
                        description=temporal,
                        severity="major",
                        resolution_suggestion="Use most recent source as authoritative"
                    ))
                    conflict_id += 1
                
                # Check for positional conflicts
                positional = self._detect_positional_conflict(content1, content2)
                if positional:
                    conflicts.append(ConflictPair(
                        conflict_id=f"conflict_{conflict_id}",
                        conflict_type=ConflictType.POSITIONAL,
                        source1={"index": i, "content": content1[:300], "metadata": src1.get("metadata", {})},
                        source2={"index": j, "content": content2[:300], "metadata": src2.get("metadata", {})},
                        description=positional,
                        severity="moderate",
                        resolution_suggestion="Present both positions to user"
                    ))
                    conflict_id += 1
        
        return conflicts
    
    def _detect_factual_conflict(self, content1: str, content2: str) -> Optional[str]:
        """Detect factual contradictions between contents."""
        c1_lower = content1.lower()
        c2_lower = content2.lower()
        
        for pos_pattern, neg_pattern in self._negation_patterns:
            pos_matches_1 = re.findall(pos_pattern, c1_lower)
            neg_matches_2 = re.findall(neg_pattern, c2_lower)
            
            if pos_matches_1 and neg_matches_2:
                return f"Potential factual conflict: Source 1 negates what Source 2 affirms"
            
            pos_matches_2 = re.findall(pos_pattern, c2_lower)
            neg_matches_1 = re.findall(neg_pattern, c1_lower)
            
            if pos_matches_2 and neg_matches_1:
                return f"Potential factual conflict: Source 2 negates what Source 1 affirms"
        
        return None
    
    def _detect_numerical_conflict(self, content1: str, content2: str) -> Optional[str]:
        """Detect conflicting numbers/statistics."""
        numbers1 = re.findall(self._number_pattern, content1)
        numbers2 = re.findall(self._number_pattern, content2)
        
        if not numbers1 or not numbers2:
            return None
        
        # Check for same-unit conflicts
        for n1, unit1 in numbers1:
            for n2, unit2 in numbers2:
                if unit1 == unit2 and unit1:  # Same unit
                    try:
                        v1, v2 = float(n1), float(n2)
                        if v1 != v2 and abs(v1 - v2) / max(v1, v2) > 0.1:  # >10% difference
                            return f"Numerical conflict: {n1}{unit1} vs {n2}{unit2}"
                    except (ValueError, TypeError):
                        pass
        
        return None
    
    def _detect_temporal_conflict(self, src1: Dict, src2: Dict) -> Optional[str]:
        """Detect temporal inconsistencies."""
        meta1 = src1.get("metadata", {})
        meta2 = src2.get("metadata", {})
        
        date1 = meta1.get("date", "")
        date2 = meta2.get("date", "")
        
        if date1 and date2:
            # Extract years
            year1 = re.search(r"(\d{4})", str(date1))
            year2 = re.search(r"(\d{4})", str(date2))
            
            if year1 and year2:
                y1, y2 = int(year1.group(1)), int(year2.group(1))
                if abs(y1 - y2) > 5:  # More than 5 years apart
                    return f"Temporal gap: Sources are {abs(y1-y2)} years apart ({y1} vs {y2})"
        
        return None
    
    def _detect_positional_conflict(self, content1: str, content2: str) -> Optional[str]:
        """Detect conflicting policy positions."""
        position_pairs = [
            ("supports", "opposes"),
            ("agrees", "disagrees"),
            ("allies", "adversaries"),
            ("cooperative", "competitive"),
            ("partner", "rival"),
            ("welcome", "condemn")
        ]
        
        c1_lower = content1.lower()
        c2_lower = content2.lower()
        
        for pos, neg in position_pairs:
            if pos in c1_lower and neg in c2_lower:
                return f"Positional conflict: '{pos}' vs '{neg}'"
            if neg in c1_lower and pos in c2_lower:
                return f"Positional conflict: '{neg}' vs '{pos}'"
        
        return None
    
    def calculate_trust_scores(self, sources: List[Dict]) -> Dict[int, float]:
        """
        Calculate trust scores for sources based on:
        - Recency
        - Source type (treaty > news)
        - Consistency with other sources
        """
        trust_scores = {}
        
        for i, src in enumerate(sources):
            score = 0.5  # Base score
            meta = src.get("metadata", {})
            
            # Recency boost
            date_str = meta.get("date", "")
            if date_str:
                year_match = re.search(r"(\d{4})", str(date_str))
                if year_match:
                    year = int(year_match.group(1))
                    if year >= 2020:
                        score += 0.2
                    elif year >= 2015:
                        score += 0.1
            
            # Source type boost
            source_type = meta.get("type", "").lower()
            if "treaty" in source_type or "agreement" in source_type:
                score += 0.2
            elif "official" in source_type or "government" in source_type:
                score += 0.15
            elif "news" in source_type:
                score += 0.05
            
            # Retrieval score consideration
            retrieval_score = src.get("score", 0.5)
            score += retrieval_score * 0.1
            
            trust_scores[i] = min(1.0, score)
        
        return trust_scores
    
    def refine_sources(self, sources: List[Dict]) -> RefinementResult:
        """
        Analyze sources for conflicts and compute trust scores.
        Returns refinement result with user-facing notes.
        """
        conflicts = self.detect_conflicts(sources)
        trust_scores = self.calculate_trust_scores(sources)
        
        user_notes = []
        
        if conflicts:
            user_notes.append(f"⚠️ {len(conflicts)} conflict(s) detected between sources")
            
            for conflict in conflicts:
                if conflict.severity == "major":
                    user_notes.append(f"🔴 Major: {conflict.description}")
                elif conflict.severity == "moderate":
                    user_notes.append(f"🟡 Moderate: {conflict.description}")
        
        return RefinementResult(
            original_sources=len(sources),
            conflicts_detected=len(conflicts),
            conflict_pairs=conflicts,
            refined_answer=None,  # Set by caller after using this info
            user_notes=user_notes,
            trust_scores=trust_scores
        )
    
    def surface_conflicts_for_user(self, conflicts: List[ConflictPair]) -> str:
        """Generate user-facing conflict summary."""
        if not conflicts:
            return "No conflicts detected in source documents."
        
        lines = ["### ⚠️ Source Conflicts Detected\n"]
        lines.append("The retrieved documents contain the following conflicts:\n")
        
        for i, conflict in enumerate(conflicts, 1):
            lines.append(f"**Conflict {i}** ({conflict.conflict_type.value}, {conflict.severity})")
            lines.append(f"- Source {conflict.source1['index']+1} vs Source {conflict.source2['index']+1}")
            lines.append(f"- {conflict.description}")
            if conflict.resolution_suggestion:
                lines.append(f"- 💡 Suggestion: {conflict.resolution_suggestion}")
            lines.append("")
        
        return "\n".join(lines)


# Singleton instance
refiner_agent = RefinerAgent()
