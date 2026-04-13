"""
Evidence Binder - Enforce Claim-to-Source Mapping
==================================================
The critical module that ensures: No evidence → No answer.

Key Principle:
"The model must map every claim to a source chunk before it can speak."

This single change dramatically improves reliability by:
1. Preventing hallucination (can't claim without source)
2. Ensuring traceability (every claim has a citation)
3. Forcing precision (vague claims get flagged)
"""

from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
import re


@dataclass
class BoundClaim:
    """A claim that has been bound to evidence."""
    claim_id: str
    claim_text: str
    source_sentence: str
    
    # Binding status
    is_grounded: bool = False
    confidence: float = 0.0
    
    # Supporting evidence
    supporting_sources: List[Dict] = field(default_factory=list)
    source_quotes: List[str] = field(default_factory=list)
    
    # Citation info
    citation_refs: List[str] = field(default_factory=list)
    
    def get_citation_string(self) -> str:
        """Get formatted citation string."""
        if not self.citation_refs:
            return "[no source]"
        return f"[{', '.join(self.citation_refs)}]"


@dataclass
class BindingResult:
    """Result of binding claims to sources."""
    original_answer: str
    claims: List[BoundClaim]
    
    # Overall status
    all_grounded: bool = False
    grounding_score: float = 0.0
    
    # Detailed metrics
    total_claims: int = 0
    grounded_claims: int = 0
    ungrounded_claims: int = 0
    
    # Action items
    ungrounded_texts: List[str] = field(default_factory=list)
    grounded_answer: Optional[str] = None
    
    def get_grounded_answer(self) -> str:
        """Get answer with only grounded claims, with citations."""
        if self.grounded_answer:
            return self.grounded_answer
        
        grounded_parts = []
        for claim in self.claims:
            if claim.is_grounded:
                grounded_parts.append(f"{claim.claim_text} {claim.get_citation_string()}")
        
        return " ".join(grounded_parts) if grounded_parts else "Insufficient evidence to answer."


class EvidenceBinder:
    """
    Enforces strict evidence binding.
    
    This is the gatekeeper that ensures:
    1. Every claim maps to a source
    2. Ungrounded claims are blocked or flagged
    3. Citations are added to grounded claims
    
    Usage:
        binder = EvidenceBinder()
        
        # After generating an answer
        result = binder.bind_claims_to_sources(answer, sources)
        
        if not result.all_grounded:
            # Either regenerate or use grounded-only version
            safe_answer = result.get_grounded_answer()
    """
    
    def __init__(self, llm_client=None, strict_mode: bool = True):
        self.llm = llm_client
        self.strict_mode = strict_mode
        
        # Claim extraction patterns
        self._claim_patterns = [
            # Factual assertions with verbs
            r'([A-Z][^.!?]*(?:is|are|was|were|has|have|will|would|should)[^.!?]*[.!?])',
            # Action statements
            r'([A-Z][^.!?]*(?:signed|ratified|enacted|declared|announced|stated)[^.!?]*[.!?])',
            # Legal references
            r'([A-Z][^.!?]*(?:Article|Section|Treaty|Agreement|Convention|Act)[^.!?]*[.!?])',
            # Quantitative claims
            r'([A-Z][^.!?]*(?:\d+[\d,]*\s*(?:percent|million|billion|trillion))[^.!?]*[.!?])',
        ]
        
        # Words that indicate hedging (less strict verification needed)
        self._hedging_words = [
            'may', 'might', 'could', 'possibly', 'perhaps', 'seems',
            'appears', 'suggests', 'indicates', 'likely', 'probably'
        ]
        
        # Minimum similarity threshold for grounding
        self._similarity_threshold = 0.35
    
    def extract_claims(self, answer: str) -> List[BoundClaim]:
        """Extract verifiable claims from an answer."""
        claims = []
        claim_id = 0
        seen_texts = set()
        
        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', answer)
        
        for sentence in sentences:
            sentence = sentence.strip()
            
            # Skip short sentences
            if len(sentence.split()) < 5:
                continue
            
            # Skip if already seen
            if sentence in seen_texts:
                continue
            seen_texts.add(sentence)
            
            # Check if sentence contains a claim
            is_claim = False
            for pattern in self._claim_patterns:
                if re.search(pattern, sentence):
                    is_claim = True
                    break
            
            if is_claim or self._is_factual_assertion(sentence):
                claims.append(BoundClaim(
                    claim_id=f"claim_{claim_id}",
                    claim_text=sentence,
                    source_sentence=sentence
                ))
                claim_id += 1
        
        return claims
    
    def _is_factual_assertion(self, sentence: str) -> bool:
        """Check if sentence contains a factual assertion."""
        factual_markers = [
            'according to', 'treaty', 'agreement', 'signed', 'ratified',
            'established', 'declares', 'affirms', 'recognizes', 'states',
            'percent', 'million', 'billion', 'article', 'section',
            'in force', 'effective', 'binding', 'obligates'
        ]
        sentence_lower = sentence.lower()
        return any(marker in sentence_lower for marker in factual_markers)
    
    def _is_hedged_claim(self, sentence: str) -> bool:
        """Check if claim is hedged (less certainty)."""
        sentence_lower = sentence.lower()
        return any(word in sentence_lower for word in self._hedging_words)
    
    def bind_claims_to_sources(
        self, 
        answer: str, 
        sources: List[Dict]
    ) -> BindingResult:
        """
        Bind each claim to supporting sources.
        
        Args:
            answer: The generated answer
            sources: List of source documents with 'content' field
            
        Returns:
            BindingResult with grounding status for each claim
        """
        # Extract claims
        claims = self.extract_claims(answer)
        
        if not claims:
            # No claims to verify
            return BindingResult(
                original_answer=answer,
                claims=[],
                all_grounded=True,
                grounding_score=1.0,
                total_claims=0,
                grounded_claims=0,
                ungrounded_claims=0
            )
        
        # Bind each claim
        grounded_count = 0
        ungrounded_texts = []
        
        for claim in claims:
            is_grounded, confidence, supporting = self._verify_claim(claim, sources)
            
            claim.is_grounded = is_grounded
            claim.confidence = confidence
            claim.supporting_sources = supporting
            
            # Extract quotes from supporting sources
            claim.source_quotes = self._extract_supporting_quotes(claim.claim_text, supporting)
            
            # Generate citation refs
            claim.citation_refs = [
                self._make_citation_ref(src, i)
                for i, src in enumerate(supporting[:3])  # Max 3 citations
            ]
            
            if is_grounded:
                grounded_count += 1
            else:
                ungrounded_texts.append(claim.claim_text)
        
        # Calculate metrics
        total = len(claims)
        grounding_score = grounded_count / total if total > 0 else 0
        all_grounded = grounded_count == total
        
        return BindingResult(
            original_answer=answer,
            claims=claims,
            all_grounded=all_grounded,
            grounding_score=grounding_score,
            total_claims=total,
            grounded_claims=grounded_count,
            ungrounded_claims=total - grounded_count,
            ungrounded_texts=ungrounded_texts
        )
    
    def _verify_claim(
        self, 
        claim: BoundClaim, 
        sources: List[Dict]
    ) -> Tuple[bool, float, List[Dict]]:
        """Verify a claim against sources."""
        supporting = []
        max_similarity = 0.0
        
        # Extract key terms from claim
        claim_words = self._extract_key_words(claim.claim_text)
        claim_phrases = self._extract_key_phrases(claim.claim_text)
        
        for source in sources:
            content = source.get("content", "")
            content_lower = content.lower()
            
            # Calculate word overlap
            source_words = set(content_lower.split())
            overlap = len(claim_words & source_words)
            word_similarity = overlap / len(claim_words) if claim_words else 0
            
            # Check for key phrases
            phrase_matches = sum(
                1 for phrase in claim_phrases 
                if phrase.lower() in content_lower
            )
            phrase_similarity = phrase_matches / len(claim_phrases) if claim_phrases else 0
            
            # Combined similarity
            similarity = (word_similarity * 0.4) + (phrase_similarity * 0.6)
            
            if similarity > self._similarity_threshold:
                supporting.append(source)
                max_similarity = max(max_similarity, similarity)
        
        # Determine grounding
        is_grounded = len(supporting) > 0 and max_similarity > self._similarity_threshold
        
        # Lower threshold for hedged claims
        if not is_grounded and self._is_hedged_claim(claim.claim_text):
            if max_similarity > self._similarity_threshold * 0.7:
                is_grounded = True
        
        return is_grounded, max_similarity, supporting
    
    def _extract_key_words(self, text: str) -> Set[str]:
        """Extract key words from text."""
        words = set(text.lower().split())
        
        # Remove stopwords
        stopwords = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'has', 'have', 'had',
            'be', 'been', 'being', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'shall', 'can', 'to', 'of', 'in',
            'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through',
            'that', 'this', 'these', 'those', 'it', 'its', 'and', 'or', 'but'
        }
        
        return words - stopwords
    
    def _extract_key_phrases(self, text: str) -> List[str]:
        """Extract key phrases from text."""
        phrases = []
        
        # Named entities (capitalized sequences)
        for match in re.finditer(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*', text):
            if len(match.group()) > 3:  # Skip short matches
                phrases.append(match.group())
        
        # Acronyms
        for match in re.finditer(r'\b[A-Z]{2,}\b', text):
            phrases.append(match.group())
        
        # Numbers and dates
        for match in re.finditer(r'\d{4}|\d+(?:\.\d+)?(?:\s*(?:percent|million|billion))?', text):
            phrases.append(match.group())
        
        # Legal references
        for match in re.finditer(r'(?:Article|Section|Chapter)\s+\d+', text):
            phrases.append(match.group())
        
        return phrases
    
    def _extract_supporting_quotes(self, claim: str, sources: List[Dict]) -> List[str]:
        """Extract relevant quotes from supporting sources."""
        quotes = []
        claim_phrases = self._extract_key_phrases(claim)
        
        for source in sources[:2]:  # Max 2 sources
            content = source.get("content", "")
            sentences = re.split(r'(?<=[.!?])\s+', content)
            
            for sentence in sentences[:10]:  # Check first 10 sentences
                if any(phrase.lower() in sentence.lower() for phrase in claim_phrases):
                    # Truncate long sentences
                    if len(sentence) > 200:
                        sentence = sentence[:200] + "..."
                    quotes.append(sentence.strip())
                    break
        
        return quotes

    def _make_citation_ref(self, source: Dict[str, Any], index: int) -> str:
        """
        Build a stable citation token.

        Preference order:
        1) Observation/evidence IDs
        2) Document ID
        3) Source label
        """
        meta = source.get("metadata", {}) if isinstance(source, dict) else {}
        for key in ("obs_id", "observation_id", "evidence_id"):
            value = meta.get(key)
            if value:
                return str(value)

        if isinstance(source, dict) and source.get("id"):
            return str(source["id"])

        source_name = meta.get("source")
        if source_name:
            return str(source_name)

        return f"source_{index + 1}"
    
    def enforce_grounding(
        self, 
        result: BindingResult,
        mode: str = "filter"
    ) -> str:
        """
        Enforce grounding policy.
        
        Modes:
        - "filter": Remove ungrounded claims, return grounded only
        - "warn": Keep all but add warnings for ungrounded
        - "block": Return error if any ungrounded claims
        """
        if result.all_grounded:
            # All good, return with citations
            return self._add_citations(result)
        
        if mode == "block":
            if self.strict_mode:
                raise ValueError(
                    f"Answer contains {result.ungrounded_claims} ungrounded claims. "
                    f"Cannot proceed in strict mode."
                )
            return "Unable to provide a fully grounded answer. Please refine the query."
        
        elif mode == "warn":
            answer = self._add_citations(result)
            warnings = [f"⚠️ Unverified: {text[:50]}..." for text in result.ungrounded_texts]
            return answer + "\n\n" + "\n".join(warnings)
        
        else:  # filter
            return result.get_grounded_answer()
    
    def _add_citations(self, result: BindingResult) -> str:
        """Add citations to grounded claims."""
        parts = []
        for claim in result.claims:
            if claim.is_grounded:
                parts.append(f"{claim.claim_text} {claim.get_citation_string()}")
            else:
                parts.append(claim.claim_text)
        
        return " ".join(parts)
    
    def get_grounding_report(self, result: BindingResult) -> Dict[str, Any]:
        """Generate a detailed grounding report."""
        return {
            "total_claims": result.total_claims,
            "grounded": result.grounded_claims,
            "ungrounded": result.ungrounded_claims,
            "grounding_score": result.grounding_score,
            "all_grounded": result.all_grounded,
            "claim_details": [
                {
                    "claim": claim.claim_text[:100],
                    "grounded": claim.is_grounded,
                    "confidence": claim.confidence,
                    "sources": len(claim.supporting_sources),
                    "citations": claim.citation_refs
                }
                for claim in result.claims
            ],
            "ungrounded_claims": result.ungrounded_texts
        }


# Singleton instance
evidence_binder = EvidenceBinder()


__all__ = [
    "EvidenceBinder",
    "evidence_binder",
    "BoundClaim",
    "BindingResult",
]
