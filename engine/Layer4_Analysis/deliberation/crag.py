"""
Corrective RAG (CRAG) Logic
Implements self-correcting retrieval with internal search when confidence is low.
Avoids "bluffs" by triggering corrective search before falling back to refusal.
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import asyncio


class RetrievalQuality(Enum):
    """Quality assessment of retrieved documents."""
    CORRECT = "correct"      # Highly relevant, sufficient
    AMBIGUOUS = "ambiguous"  # Partially relevant, needs refinement
    INCORRECT = "incorrect"  # Irrelevant, needs corrective search


class CRAGAction(Enum):
    """Actions to take based on retrieval quality."""
    USE_RETRIEVED = "use_retrieved"    # Use current results
    REFINE_QUERY = "refine_query"      # Reformulate and retry
    WEB_SEARCH = "web_search"          # Fall back to web search
    REFUSE = "refuse"                  # Cannot answer reliably


@dataclass
class CRAGResult:
    """Result of CRAG evaluation and correction."""
    original_query: str
    refined_query: Optional[str]
    quality: RetrievalQuality
    action_taken: CRAGAction
    original_docs: List[Dict]
    refined_docs: List[Dict]
    confidence_before: float
    confidence_after: float
    iterations: int
    explanation: str


class CRAGEngine:
    """
    Corrective RAG Engine.
    
    Implements:
    1. Retrieval quality evaluation
    2. Query refinement for ambiguous results
    3. Internal knowledge search as fallback
    4. Web search integration for correction
    5. Graceful refusal when correction fails
    """
    
    # Thresholds
    CORRECT_THRESHOLD = 0.75    # Quality score for "correct" retrieval
    AMBIGUOUS_THRESHOLD = 0.40  # Below this = "incorrect"
    MAX_CORRECTION_ITERATIONS = 3
    MIN_SOURCES_REQUIRED = 2
    
    def __init__(self, retriever=None, web_search=None):
        self.retriever = retriever
        self.web_search = web_search
        
        # Query refinement patterns
        self._refinement_strategies = [
            self._expand_acronyms,
            self._add_context_terms,
            self._simplify_query,
            self._extract_entities
        ]
    
    async def evaluate_and_correct(
        self,
        query: str,
        retrieved_docs: List[Dict],
        context: Dict[str, Any] = None
    ) -> CRAGResult:
        """
        Main CRAG pipeline: evaluate retrieval quality and correct if needed.
        """
        # Initial quality assessment
        quality, confidence = self._assess_retrieval_quality(query, retrieved_docs)
        
        result = CRAGResult(
            original_query=query,
            refined_query=None,
            quality=quality,
            action_taken=CRAGAction.USE_RETRIEVED,
            original_docs=retrieved_docs,
            refined_docs=[],
            confidence_before=confidence,
            confidence_after=confidence,
            iterations=0,
            explanation=""
        )
        
        # If correct, use as-is
        if quality == RetrievalQuality.CORRECT:
            result.explanation = "Retrieved documents are highly relevant"
            return result
        
        # If ambiguous, try query refinement
        if quality == RetrievalQuality.AMBIGUOUS:
            refined_result = await self._refine_and_retry(query, retrieved_docs, context)
            if refined_result:
                return refined_result
        
        # If incorrect or refinement failed, try web search
        if self.web_search and quality == RetrievalQuality.INCORRECT:
            web_result = await self._web_search_correction(query, context)
            if web_result:
                return web_result
        
        # All corrections failed - refuse
        result.action_taken = CRAGAction.REFUSE
        result.explanation = (
            f"Unable to find reliable sources after {result.iterations} correction attempts. "
            f"Retrieval confidence: {confidence:.2f}"
        )
        
        return result
    
    def _assess_retrieval_quality(
        self,
        query: str,
        documents: List[Dict]
    ) -> Tuple[RetrievalQuality, float]:
        """
        Assess the quality of retrieved documents.
        Returns (quality_level, confidence_score).
        """
        if not documents:
            return RetrievalQuality.INCORRECT, 0.0
        
        # Calculate relevance scores
        query_words = set(query.lower().split())
        query_words -= {"what", "is", "the", "how", "when", "where", "who", "a", "an", "of"}
        
        relevance_scores = []
        
        for doc in documents:
            content = doc.get("content", "").lower()
            doc_words = set(content.split())
            
            # Word overlap
            overlap = len(query_words & doc_words)
            max_possible = len(query_words)
            
            if max_possible > 0:
                relevance = overlap / max_possible
            else:
                relevance = 0.5
            
            # Boost for retrieval score if present
            retrieval_score = doc.get("score", 0.5)
            combined = (relevance * 0.6) + (retrieval_score * 0.4)
            
            relevance_scores.append(combined)
        
        # Aggregate score
        avg_score = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0
        max_score = max(relevance_scores) if relevance_scores else 0
        
        # Weight towards max (best document matters most)
        final_score = (avg_score * 0.4) + (max_score * 0.6)
        
        # Penalize for too few sources
        if len(documents) < self.MIN_SOURCES_REQUIRED:
            final_score *= 0.8
        
        # Determine quality level
        if final_score >= self.CORRECT_THRESHOLD:
            return RetrievalQuality.CORRECT, final_score
        elif final_score >= self.AMBIGUOUS_THRESHOLD:
            return RetrievalQuality.AMBIGUOUS, final_score
        else:
            return RetrievalQuality.INCORRECT, final_score
    
    async def _refine_and_retry(
        self,
        query: str,
        original_docs: List[Dict],
        context: Dict[str, Any] = None
    ) -> Optional[CRAGResult]:
        """
        Refine query and retry retrieval.
        """
        best_result = None
        best_confidence = 0.0
        
        for iteration, strategy in enumerate(self._refinement_strategies):
            if iteration >= self.MAX_CORRECTION_ITERATIONS:
                break
            
            # Refine query
            refined_query = strategy(query, context)
            
            if refined_query == query:
                continue  # No change
            
            # Retry retrieval
            if self.retriever:
                new_docs = await self._retrieve(refined_query)
            else:
                # Simulate using original docs with re-scoring
                new_docs = self._rescore_documents(refined_query, original_docs)
            
            # Re-assess
            quality, confidence = self._assess_retrieval_quality(refined_query, new_docs)
            
            if quality == RetrievalQuality.CORRECT or confidence > best_confidence:
                best_confidence = confidence
                best_result = CRAGResult(
                    original_query=query,
                    refined_query=refined_query,
                    quality=quality,
                    action_taken=CRAGAction.REFINE_QUERY,
                    original_docs=original_docs,
                    refined_docs=new_docs,
                    confidence_before=0.0,  # Will be set
                    confidence_after=confidence,
                    iterations=iteration + 1,
                    explanation=f"Query refined using {strategy.__name__}"
                )
                
                if quality == RetrievalQuality.CORRECT:
                    return best_result
        
        return best_result
    
    async def _web_search_correction(
        self,
        query: str,
        context: Dict[str, Any] = None
    ) -> Optional[CRAGResult]:
        """
        Fall back to web search for correction.
        """
        if not self.web_search:
            return None
        
        try:
            web_results = await self.web_search(query)
            
            if not web_results:
                return None
            
            quality, confidence = self._assess_retrieval_quality(query, web_results)
            
            return CRAGResult(
                original_query=query,
                refined_query=None,
                quality=quality,
                action_taken=CRAGAction.WEB_SEARCH,
                original_docs=[],
                refined_docs=web_results,
                confidence_before=0.0,
                confidence_after=confidence,
                iterations=1,
                explanation="Corrected using web search results"
            )
        except Exception:
            return None
    
    async def _retrieve(self, query: str) -> List[Dict]:
        """Retrieve documents using configured retriever."""
        if self.retriever:
            return await self.retriever.retrieve(query)
        return []
    
    def _rescore_documents(self, query: str, docs: List[Dict]) -> List[Dict]:
        """Re-score documents against refined query."""
        query_words = set(query.lower().split())
        
        rescored = []
        for doc in docs:
            content = doc.get("content", "").lower()
            overlap = len(query_words & set(content.split()))
            new_score = overlap / len(query_words) if query_words else 0
            
            rescored.append({
                **doc,
                "score": new_score,
                "rescored": True
            })
        
        return sorted(rescored, key=lambda x: x.get("score", 0), reverse=True)
    
    # Query refinement strategies
    
    def _expand_acronyms(self, query: str, context: Dict = None) -> str:
        """Expand common acronyms."""
        expansions = {
            "UN": "United Nations",
            "NATO": "North Atlantic Treaty Organization",
            "EU": "European Union",
            "WTO": "World Trade Organization",
            "IMF": "International Monetary Fund",
            "ASEAN": "Association of Southeast Asian Nations",
            "QUAD": "Quadrilateral Security Dialogue",
            "BRICS": "Brazil Russia India China South Africa",
            "SCO": "Shanghai Cooperation Organisation",
            "MEA": "Ministry of External Affairs",
            "MoU": "Memorandum of Understanding"
        }
        
        words = query.split()
        expanded = []
        
        for word in words:
            upper = word.upper()
            if upper in expansions:
                expanded.append(f"{word} ({expansions[upper]})")
            else:
                expanded.append(word)
        
        return " ".join(expanded)
    
    def _add_context_terms(self, query: str, context: Dict = None) -> str:
        """Add contextual terms to query."""
        if not context:
            return query
        
        additions = []
        
        if "jurisdiction" in context:
            additions.append(context["jurisdiction"])
        if "year" in context:
            additions.append(str(context["year"]))
        if "topic" in context:
            additions.append(context["topic"])
        
        if additions:
            return f"{query} {' '.join(additions)}"
        
        return query
    
    def _simplify_query(self, query: str, context: Dict = None) -> str:
        """Simplify complex query to core terms."""
        # Remove question words and common stopwords
        stopwords = {
            "what", "is", "the", "how", "when", "where", "who", "which",
            "can", "could", "would", "should", "does", "do", "did",
            "a", "an", "of", "in", "on", "at", "to", "for", "with"
        }
        
        words = query.lower().split()
        simplified = [w for w in words if w not in stopwords]
        
        return " ".join(simplified)
    
    def _extract_entities(self, query: str, context: Dict = None) -> str:
        """Extract key entities from query."""
        import re
        
        # Find capitalized words (likely entities)
        entities = re.findall(r'\b[A-Z][a-zA-Z]*\b', query)
        
        # Find dates/years
        dates = re.findall(r'\b\d{4}\b', query)
        
        # Find treaty/agreement references
        treaties = re.findall(r'(?:Treaty|Agreement|Convention|Protocol)\s+(?:of\s+)?[A-Za-z]+', query)
        
        terms = entities + dates + treaties
        
        if terms:
            return " ".join(terms)
        
        return query
    
    def get_correction_stats(self) -> Dict[str, Any]:
        """Get statistics on correction effectiveness."""
        return {
            "thresholds": {
                "correct": self.CORRECT_THRESHOLD,
                "ambiguous": self.AMBIGUOUS_THRESHOLD
            },
            "strategies": [s.__name__ for s in self._refinement_strategies],
            "max_iterations": self.MAX_CORRECTION_ITERATIONS,
            "min_sources": self.MIN_SOURCES_REQUIRED
        }


# Singleton instance
crag_engine = CRAGEngine()


# Quick correction function
async def correct_retrieval(
    query: str,
    documents: List[Dict],
    context: Dict = None
) -> Tuple[List[Dict], float, str]:
    """
    Quick interface for CRAG correction.
    Returns (corrected_docs, confidence, explanation).
    """
    result = await crag_engine.evaluate_and_correct(query, documents, context)
    
    docs = result.refined_docs if result.refined_docs else result.original_docs
    
    return docs, result.confidence_after, result.explanation
