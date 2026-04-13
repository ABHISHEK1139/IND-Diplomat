"""
Evidence Registry - Track Evidence Requirements and Fulfillment
================================================================
Tracks what evidence exists and what's missing for a query.

Key Principle:
"The system must know what evidence it has before deciding to answer"
"""

from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class RequirementStatus(Enum):
    """Status of an evidence requirement."""
    PENDING = "pending"
    PARTIALLY_SATISFIED = "partially_satisfied"
    SATISFIED = "satisfied"
    UNSATISFIABLE = "unsatisfiable"


@dataclass
class EvidenceRequirement:
    """A single evidence requirement."""
    requirement_id: str
    description: str
    required_type: str  # "legal", "factual", "temporal", "statistical"
    importance: float   # 0-1, how critical is this requirement
    
    # Status tracking
    is_satisfied: bool = False
    status: RequirementStatus = RequirementStatus.PENDING
    satisfaction_score: float = 0.0
    
    # Supporting evidence
    supporting_sources: List[str] = field(default_factory=list)
    supporting_documents: List[Dict] = field(default_factory=list)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    satisfied_at: Optional[datetime] = None


@dataclass
class SufficiencyResult:
    """Result of checking evidence sufficiency."""
    is_sufficient: bool
    overall_score: float
    requirements_total: int
    requirements_satisfied: int
    requirements_partial: int
    requirements_missing: int
    
    # Detailed breakdown
    requirement_scores: Dict[str, float] = field(default_factory=dict)
    gaps: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    # Thresholds used
    sufficiency_threshold: float = 0.7
    
    def can_answer(self) -> bool:
        """Check if we have enough evidence to answer."""
        return self.is_sufficient and self.overall_score >= self.sufficiency_threshold


class EvidenceRegistry:
    """
    Tracks evidence requirements and their fulfillment.
    
    This is the system's memory of what evidence it needs
    and what it has already found.
    
    Usage:
        registry = EvidenceRegistry()
        
        # Add requirements based on query analysis
        registry.add_requirement(EvidenceRequirement(
            requirement_id="req_1",
            description="Treaty text for RCEP",
            required_type="legal",
            importance=0.9
        ))
        
        # Check sufficiency after retrieval
        result = registry.check_sufficiency()
        if result.can_answer():
            # Proceed to generate answer
            ...
    """
    
    def __init__(self):
        self.requirements: Dict[str, EvidenceRequirement] = {}
        self.documents: Dict[str, Dict] = {}  # doc_id -> document
        self._sufficiency_threshold = 0.7
    
    def add_requirement(self, requirement: EvidenceRequirement):
        """Add an evidence requirement."""
        self.requirements[requirement.requirement_id] = requirement
        print(f"[EvidenceRegistry] Added requirement: {requirement.description}")
    
    def add_requirements_from_analysis(self, analysis) -> List[EvidenceRequirement]:
        """Add requirements based on query analysis."""
        requirements = []
        
        # Map evidence types to requirements
        for i, evidence_type in enumerate(analysis.required_evidence):
            req = EvidenceRequirement(
                requirement_id=f"req_{i}_{evidence_type.value}",
                description=f"Need {evidence_type.value} for: {analysis.original_query[:50]}",
                required_type=evidence_type.value,
                importance=0.8 if i == 0 else 0.6  # First is most important
            )
            self.add_requirement(req)
            requirements.append(req)
        
        # Add entity-specific requirements
        for j, entity in enumerate(analysis.entities):
            if entity["type"] == "treaty":
                req = EvidenceRequirement(
                    requirement_id=f"req_entity_{j}_{entity['normalized']}",
                    description=f"Evidence about {entity['text']}",
                    required_type="legal",
                    importance=0.9
                )
                self.add_requirement(req)
                requirements.append(req)
        
        return requirements
    
    def register_document(self, doc_id: str, document: Dict):
        """Register a retrieved document."""
        self.documents[doc_id] = document
        self._update_requirements_with_document(document)
    
    def register_documents(self, documents: List[Dict]):
        """Register multiple documents."""
        for i, doc in enumerate(documents):
            doc_id = doc.get("id", f"doc_{i}_{hash(str(doc))}")
            self.register_document(doc_id, doc)
    
    def _update_requirements_with_document(self, document: Dict):
        """Update requirement satisfaction based on new document."""
        doc_type = document.get("metadata", {}).get("type", "unknown")
        doc_content = document.get("content", "")
        doc_source = document.get("metadata", {}).get("source", "unknown")
        
        for req_id, req in self.requirements.items():
            if req.is_satisfied:
                continue
            
            # Check if document type matches requirement
            matches = self._document_matches_requirement(document, req)
            
            if matches:
                req.supporting_documents.append(document)
                req.supporting_sources.append(doc_source)
                
                # Update satisfaction score
                req.satisfaction_score = min(1.0, req.satisfaction_score + 0.3)
                
                if req.satisfaction_score >= 0.7:
                    req.is_satisfied = True
                    req.status = RequirementStatus.SATISFIED
                    req.satisfied_at = datetime.now()
                elif req.satisfaction_score > 0:
                    req.status = RequirementStatus.PARTIALLY_SATISFIED
    
    def _document_matches_requirement(self, document: Dict, requirement: EvidenceRequirement) -> bool:
        """Check if a document matches a requirement."""
        doc_type = document.get("metadata", {}).get("type", "unknown")
        
        # Type mapping
        type_matches = {
            "legal": ["treaty", "legal", "law", "agreement"],
            "treaty_text": ["treaty", "legal"],
            "legal_provision": ["legal", "law", "provision"],
            "official_statement": ["statement", "press", "official"],
            "news_report": ["news", "report", "article"],
            "statistical_data": ["data", "statistics", "economic"],
            "historical_record": ["historical", "archive", "record"],
            "expert_analysis": ["analysis", "research", "report"],
        }
        
        req_type = requirement.required_type.lower()
        acceptable_types = type_matches.get(req_type, [req_type])
        
        return doc_type.lower() in acceptable_types or any(
            t in doc_type.lower() for t in acceptable_types
        )
    
    def check_sufficiency(self) -> SufficiencyResult:
        """Check if we have sufficient evidence to answer."""
        if not self.requirements:
            return SufficiencyResult(
                is_sufficient=True,
                overall_score=1.0,
                requirements_total=0,
                requirements_satisfied=0,
                requirements_partial=0,
                requirements_missing=0
            )
        
        satisfied = 0
        partial = 0
        missing = 0
        weighted_score = 0.0
        total_weight = 0.0
        requirement_scores = {}
        gaps = []
        recommendations = []
        
        for req_id, req in self.requirements.items():
            requirement_scores[req_id] = req.satisfaction_score
            total_weight += req.importance
            weighted_score += req.satisfaction_score * req.importance
            
            if req.status == RequirementStatus.SATISFIED:
                satisfied += 1
            elif req.status == RequirementStatus.PARTIALLY_SATISFIED:
                partial += 1
                gaps.append(f"Partially satisfied: {req.description}")
            else:
                missing += 1
                gaps.append(f"Missing: {req.description}")
                recommendations.append(f"Search for {req.required_type} evidence")
        
        overall_score = weighted_score / total_weight if total_weight > 0 else 0
        is_sufficient = overall_score >= self._sufficiency_threshold
        
        return SufficiencyResult(
            is_sufficient=is_sufficient,
            overall_score=overall_score,
            requirements_total=len(self.requirements),
            requirements_satisfied=satisfied,
            requirements_partial=partial,
            requirements_missing=missing,
            requirement_scores=requirement_scores,
            gaps=gaps,
            recommendations=recommendations,
            sufficiency_threshold=self._sufficiency_threshold
        )
    
    def get_missing_requirements(self) -> List[EvidenceRequirement]:
        """Get list of unsatisfied requirements."""
        return [
            req for req in self.requirements.values()
            if not req.is_satisfied
        ]
    
    def get_evidence_summary(self) -> Dict[str, Any]:
        """Get summary of evidence state."""
        result = self.check_sufficiency()
        
        return {
            "total_requirements": result.requirements_total,
            "satisfied": result.requirements_satisfied,
            "partial": result.requirements_partial,
            "missing": result.requirements_missing,
            "overall_score": result.overall_score,
            "is_sufficient": result.is_sufficient,
            "can_answer": result.can_answer(),
            "gaps": result.gaps,
            "documents_collected": len(self.documents)
        }
    
    def reset(self):
        """Reset the registry for a new query."""
        self.requirements.clear()
        self.documents.clear()


# Singleton instance
evidence_registry = EvidenceRegistry()


__all__ = [
    "EvidenceRegistry",
    "EvidenceRequirement",
    "SufficiencyResult",
    "RequirementStatus",
    "evidence_registry",
]
