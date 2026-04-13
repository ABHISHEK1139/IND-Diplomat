"""
Document Classifier - Automatic Document Type Detection
=========================================================
Classifies documents into foundational (legal) vs dynamic (event).
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import re


class DocumentType(Enum):
    """Categories of diplomatic documents."""
    # Legal/Foundational
    TREATY = "treaty"
    LAW = "law"
    AGREEMENT = "agreement"
    CONVENTION = "convention"
    PROTOCOL = "protocol"
    
    # Event/Dynamic
    NEWS = "news"
    STATEMENT = "statement"
    PRESS_RELEASE = "press_release"
    SPEECH = "speech"
    
    # Economic
    TRADE_DATA = "trade_data"
    SANCTION = "sanction"
    
    # Strategic
    ANALYSIS = "analysis"
    REPORT = "report"
    
    # Default
    UNKNOWN = "unknown"


@dataclass
class ClassificationResult:
    """Result of classifying a document."""
    document_type: DocumentType
    confidence: float
    category: str  # "foundational", "dynamic", "economic", "strategic"
    reasoning: str
    metadata_extracted: Dict[str, Any]


class DocumentClassifier:
    """
    Automatically classifies documents by type.
    
    Key Distinction:
    - Foundational: Changes rarely, provides rules (treaties, laws)
    - Dynamic: Changes frequently, provides context (news, statements)
    
    Usage:
        classifier = DocumentClassifier()
        result = classifier.classify(document)
        
        print(f"Type: {result.document_type}")
        print(f"Category: {result.category}")
    """
    
    def __init__(self):
        # Classification patterns
        self._type_patterns = {
            DocumentType.TREATY: [
                r'\btreaty\b', r'\bconvention\b', r'\bprotocol\b',
                r'\bratified\b', r'\bentry into force\b', r'\barticle\s+\d+',
                r'\bsignatory\b', r'\bparties\b', r'\bdone at\b'
            ],
            DocumentType.LAW: [
                r'\bact\b', r'\blegislation\b', r'\bstatute\b',
                r'\benacted\b', r'\blaw no\.\b', r'\bsection\s+\d+'
            ],
            DocumentType.AGREEMENT: [
                r'\bagreement\b', r'\bmou\b', r'\bmemorandum\b',
                r'\bsigned between\b', r'\bparties agree\b'
            ],
            DocumentType.NEWS: [
                r'\breported\b', r'\bnews\b', r'\baccording to\b',
                r'\bsources said\b', r'\bconfirmed\b', r'\balleged\b'
            ],
            DocumentType.STATEMENT: [
                r'\bstatement\b', r'\bannounced\b', r'\bdeclared\b',
                r'\bspokesperson\b', r'\bministry of\b'
            ],
            DocumentType.PRESS_RELEASE: [
                r'\bpress release\b', r'\bfor immediate release\b',
                r'\bmedia advisory\b', r'\bpress information\b'
            ],
            DocumentType.SPEECH: [
                r'\baddressed\b', r'\bremarks\b', r'\bspeech by\b',
                r'\bhonorable\b', r'\besteemed\b'
            ],
            DocumentType.TRADE_DATA: [
                r'\bexports?\b', r'\bimports?\b', r'\btrade balance\b',
                r'\btariff\b', r'\bquota\b', r'\bduty\b'
            ],
            DocumentType.SANCTION: [
                r'\bsanction\b', r'\bembargo\b', r'\brestriction\b',
                r'\bblacklist\b', r'\bban on\b'
            ],
            DocumentType.ANALYSIS: [
                r'\banalysis\b', r'\bassessment\b', r'\bimplications\b',
                r'\bscenario\b', r'\bforecast\b'
            ],
            DocumentType.REPORT: [
                r'\breport\b', r'\bfindings\b', r'\brecommendations\b',
                r'\bconclusion\b', r'\bexecutive summary\b'
            ]
        }
        
        # Category mapping
        self._type_to_category = {
            DocumentType.TREATY: "foundational",
            DocumentType.LAW: "foundational",
            DocumentType.AGREEMENT: "foundational",
            DocumentType.CONVENTION: "foundational",
            DocumentType.PROTOCOL: "foundational",
            DocumentType.NEWS: "dynamic",
            DocumentType.STATEMENT: "dynamic",
            DocumentType.PRESS_RELEASE: "dynamic",
            DocumentType.SPEECH: "dynamic",
            DocumentType.TRADE_DATA: "economic",
            DocumentType.SANCTION: "economic",
            DocumentType.ANALYSIS: "strategic",
            DocumentType.REPORT: "strategic",
            DocumentType.UNKNOWN: "dynamic"
        }
    
    def classify(self, document: Dict) -> ClassificationResult:
        """
        Classify a document by type.
        
        Args:
            document: Document with 'content' and optional 'metadata'
            
        Returns:
            ClassificationResult with type and category
        """
        content = document.get("content", "")
        metadata = document.get("metadata", {})
        
        # If metadata already has type, use it
        if "type" in metadata:
            existing_type = metadata["type"].lower()
            for doc_type in DocumentType:
                if doc_type.value == existing_type:
                    return ClassificationResult(
                        document_type=doc_type,
                        confidence=1.0,
                        category=self._type_to_category[doc_type],
                        reasoning="Type provided in metadata",
                        metadata_extracted={}
                    )
        
        # Pattern-based classification
        scores = self._score_patterns(content)
        
        if not scores:
            return ClassificationResult(
                document_type=DocumentType.UNKNOWN,
                confidence=0.3,
                category="dynamic",
                reasoning="No matching patterns found",
                metadata_extracted={}
            )
        
        # Get best match
        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]
        
        # Extract additional metadata
        extracted = self._extract_metadata(content, best_type)
        
        return ClassificationResult(
            document_type=best_type,
            confidence=min(1.0, best_score / 5),  # Normalize
            category=self._type_to_category[best_type],
            reasoning=f"Matched {int(best_score)} patterns for {best_type.value}",
            metadata_extracted=extracted
        )
    
    def _score_patterns(self, content: str) -> Dict[DocumentType, float]:
        """Score content against all type patterns."""
        content_lower = content.lower()
        scores = {}
        
        for doc_type, patterns in self._type_patterns.items():
            score = sum(
                len(re.findall(pattern, content_lower, re.IGNORECASE))
                for pattern in patterns
            )
            if score > 0:
                scores[doc_type] = score
        
        return scores
    
    def _extract_metadata(
        self, 
        content: str, 
        doc_type: DocumentType
    ) -> Dict[str, Any]:
        """Extract relevant metadata based on document type."""
        extracted = {}
        
        # Extract dates
        date_match = re.search(r'\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b', content)
        if date_match:
            extracted["date_found"] = date_match.group(1)
        
        # For treaties, extract article numbers
        if doc_type in [DocumentType.TREATY, DocumentType.LAW]:
            articles = re.findall(r'Article\s+(\d+)', content, re.IGNORECASE)
            if articles:
                extracted["articles_mentioned"] = list(set(articles))[:10]
        
        # For statements, extract speaker
        if doc_type in [DocumentType.STATEMENT, DocumentType.SPEECH]:
            speaker_match = re.search(
                r'(?:Minister|Secretary|Ambassador|Spokesperson)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                content
            )
            if speaker_match:
                extracted["speaker"] = speaker_match.group(1)
        
        return extracted
    
    def classify_batch(
        self, 
        documents: List[Dict]
    ) -> Dict[str, List[Dict]]:
        """
        Classify multiple documents and group by category.
        
        Returns:
            Dict mapping category to list of documents
        """
        grouped = {
            "foundational": [],
            "dynamic": [],
            "economic": [],
            "strategic": []
        }
        
        for doc in documents:
            result = self.classify(doc)
            doc_with_classification = doc.copy()
            doc_with_classification["_classification"] = {
                "type": result.document_type.value,
                "category": result.category,
                "confidence": result.confidence
            }
            grouped[result.category].append(doc_with_classification)
        
        return grouped
    
    def is_foundational(self, document: Dict) -> bool:
        """Check if document is foundational (legal/rules)."""
        result = self.classify(document)
        return result.category == "foundational"
    
    def is_dynamic(self, document: Dict) -> bool:
        """Check if document is dynamic (news/events)."""
        result = self.classify(document)
        return result.category == "dynamic"


# Singleton instance
document_classifier = DocumentClassifier()


__all__ = [
    "DocumentClassifier",
    "document_classifier",
    "DocumentType",
    "ClassificationResult",
]
