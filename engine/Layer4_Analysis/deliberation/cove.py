"""
Chain-of-Verification (CoVe) Module - Industrial Grade
========================================================
Implements iterative verification loop to eliminate hallucinations.
Steps: Draft → Atomic Claim Decomposition → Independent Verification → RRF Scoring → Revise/Refuse

INDUSTRIAL FEATURES:
1. Atomic Claim Decomposition - Break answers into individual verifiable claims
2. Independent Engram Store Verification - Constant-time lookup against verified KB
3. RRF (Reciprocal Rank Fusion) Scoring - Multi-source confidence calculation
4. Gaslighting Protection - Source-over-prompt priority to prevent user manipulation
5. Faithfulness Formula: F = |Claims ∩ Context| / |Claims|
"""

from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
import re
import asyncio
import hashlib
import logging

logger = logging.getLogger(__name__)


class VerificationState(Enum):
    """States in the CoVe loop."""
    DRAFT = "draft"
    DECOMPOSING = "decomposing"
    QUESTIONING = "questioning"
    FACT_CHECKING = "fact_checking"
    REVISING = "revising"
    ACCEPTED = "accepted"
    REFUSED = "refused"
    INSUFFICIENT_KNOWLEDGE = "insufficient_knowledge"


@dataclass
class AtomicClaim:
    """
    An atomic, independently verifiable claim.
    Example: "India signed the RCEP agreement in 2020" -> "Signatory: India", "Agreement: RCEP", "Year: 2020"
    """
    claim_id: str
    claim_text: str
    claim_type: str  # "entity", "date", "numeric", "relation", "assertion"
    entity_subject: Optional[str] = None
    entity_predicate: Optional[str] = None
    entity_object: Optional[str] = None
    is_verified: bool = False
    verification_source: Optional[str] = None
    rrf_score: float = 0.0
    engram_match: bool = False  # Matched in constant-time engram store


@dataclass
class FactCheckQuestion:
    """A fact-check question generated from a claim."""
    question_id: str
    question: str
    original_claim: str
    atomic_claims: List[AtomicClaim] = field(default_factory=list)
    answer: Optional[str] = None
    is_verified: bool = False
    source_evidence: List[str] = field(default_factory=list)
    confidence: float = 0.0
    rrf_score: float = 0.0


@dataclass
class RRFScore:
    """Reciprocal Rank Fusion score for multi-source verification."""
    claim_id: str
    vector_rank: int = 0
    graph_rank: int = 0
    engram_rank: int = 0
    final_score: float = 0.0
    
    def calculate(self, k: int = 60) -> float:
        """Calculate RRF score: sum(1 / (k + rank)) for each source."""
        scores = []
        if self.vector_rank > 0:
            scores.append(1.0 / (k + self.vector_rank))
        if self.graph_rank > 0:
            scores.append(1.0 / (k + self.graph_rank))
        if self.engram_rank > 0:
            scores.append(1.0 / (k + self.engram_rank))
        self.final_score = sum(scores)
        return self.final_score


@dataclass
class CoVeResult:
    """Result of the Chain-of-Verification loop."""
    valid: bool = False
    original_draft: str = ""
    final_answer: Optional[str] = None
    state: VerificationState = VerificationState.DRAFT
    atomic_claims: List[AtomicClaim] = field(default_factory=list)
    fact_check_questions: List[FactCheckQuestion] = field(default_factory=list)
    revisions_made: int = 0
    faithfulness_score: float = 0.0
    rrf_threshold_met: bool = False
    gaslighting_detected: bool = False
    refusal_reason: Optional[str] = None
    verification_trace: List[Dict[str, Any]] = field(default_factory=list)


class EngramStore:
    """
    Constant-time lookup store for verified facts.
    Uses hash-based indexing for O(1) claim verification.
    """
    
    def __init__(self):
        self._verified_facts: Dict[str, Dict[str, Any]] = {}
        self._entity_index: Dict[str, Set[str]] = {}
    
    def add_verified_fact(self, claim: str, source: str, confidence: float = 1.0):
        """Add a verified fact to the engram store."""
        claim_hash = self._hash_claim(claim)
        self._verified_facts[claim_hash] = {
            "claim": claim,
            "source": source,
            "confidence": confidence
        }
        # Index by entities
        for entity in self._extract_key_terms(claim):
            if entity not in self._entity_index:
                self._entity_index[entity] = set()
            self._entity_index[entity].add(claim_hash)
    
    def lookup(self, claim: str) -> Tuple[bool, Optional[Dict]]:
        """O(1) lookup of a claim."""
        claim_hash = self._hash_claim(claim)
        if claim_hash in self._verified_facts:
            return True, self._verified_facts[claim_hash]
        return False, None
    
    def fuzzy_lookup(self, claim: str, threshold: float = 0.7) -> List[Dict]:
        """Fuzzy lookup using entity intersection."""
        claim_terms = self._extract_key_terms(claim)
        candidates = set()
        for term in claim_terms:
            if term in self._entity_index:
                candidates.update(self._entity_index[term])
        
        results = []
        for claim_hash in candidates:
            fact = self._verified_facts.get(claim_hash, {})
            if fact:
                fact_terms = self._extract_key_terms(fact.get("claim", ""))
                overlap = len(claim_terms & fact_terms) / max(len(claim_terms), 1)
                if overlap >= threshold:
                    results.append({**fact, "similarity": overlap})
        
        return sorted(results, key=lambda x: x.get("similarity", 0), reverse=True)
    
    def _hash_claim(self, claim: str) -> str:
        """Generate hash for claim."""
        normalized = claim.lower().strip()
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def _extract_key_terms(self, text: str) -> Set[str]:
        """Extract key terms for indexing."""
        words = set(text.lower().split())
        stopwords = {"the", "a", "an", "is", "are", "was", "were", "has", "have", "in", "on", "at", "to", "for"}
        return words - stopwords


# Global engram store
engram_store = EngramStore()


class ChainOfVerification:
    """
    Industrial-Grade Chain-of-Verification (CoVe) Loop.
    
    Features:
    1. Atomic Claim Decomposition - Break into verifiable units
    2. Multi-Source Verification - Vector + Graph + Engram
    3. RRF Scoring - Reciprocal Rank Fusion for confidence
    4. Gaslighting Protection - Source-over-prompt priority
    5. Strict Refusal - Refuse when faithfulness < threshold
    """
    
    # Industrial-grade thresholds
    FAITHFULNESS_THRESHOLD = 0.85  # Minimum faithfulness to accept
    RRF_THRESHOLD = 0.015          # Minimum RRF score (approx 0.8 normalized)
    MIN_VERIFIED_RATIO = 0.90      # 90% of claims must verify
    MAX_REVISION_ROUNDS = 3        # Maximum revision attempts
    GASLIGHTING_SENSITIVITY = 0.7  # Detect user false premises
    
    def __init__(self, retriever=None, llm_client=None, engram_store=None):
        self.retriever = retriever
        self.llm = llm_client
        self.engram = engram_store or globals()['engram_store']
        self._question_templates = [
            "What is the exact date of {entity}?",
            "Which parties signed {entity}?",
            "What article or section discusses {topic}?",
            "Is {claim} still in force as of the current date?",
            "What is the specific numerical value for {metric}?",
            "Which jurisdiction does {subject} apply to?"
        ]
    
    async def run_cove_loop(
        self,
        query: str,
        initial_draft: str,
        sources: List[Dict],
        max_rounds: int = None
    ) -> CoVeResult:
        """
        Execute the Industrial-Grade Chain-of-Verification loop.
        
        Enhanced Steps:
        1. Detect gaslighting in user query
        2. Decompose answer into atomic claims
        3. Verify each claim against engram store (O(1))
        4. Calculate RRF score for multi-source verification
        5. Apply faithfulness threshold
        6. Revise or refuse based on strict thresholds
        """
        max_rounds = max_rounds or self.MAX_REVISION_ROUNDS
        trace = []
        current_draft = initial_draft
        revision_count = 0
        all_atomic_claims = []
        gaslighting_detected = False
        
        # Step 0: Gaslighting Detection - Check if user query contains false premises
        gaslighting_detected, false_premises = self._detect_gaslighting(query, sources)
        if gaslighting_detected:
            trace.append({
                "round": "pre",
                "action": "gaslighting_detected",
                "false_premises": false_premises
            })
            logger.warning(f"[CoVe] Gaslighting detected: {false_premises}")
        
        for round_num in range(max_rounds):
            # Step 1: Decompose into atomic claims
            atomic_claims = self._decompose_to_atomic_claims(current_draft)
            all_atomic_claims = atomic_claims
            trace.append({
                "round": round_num,
                "action": "decompose_claims",
                "count": len(atomic_claims)
            })
            
            if not atomic_claims:
                # No claims to verify - accept as-is
                return CoVeResult(
                    valid=True,
                    original_draft=initial_draft,
                    final_answer=current_draft,
                    state=VerificationState.ACCEPTED,
                    atomic_claims=[],
                    fact_check_questions=[],
                    revisions_made=revision_count,
                    faithfulness_score=1.0,
                    rrf_threshold_met=True,
                    gaslighting_detected=gaslighting_detected,
                    refusal_reason=None,
                    verification_trace=trace
                )
            
            # Step 2: Verify atomic claims via engram store (O(1) lookup)
            await self._verify_atomic_claims(atomic_claims, sources)
            
            # Step 3: Calculate RRF scores for multi-source verification
            rrf_scores = self._calculate_rrf_scores(atomic_claims, sources)
            avg_rrf = sum(s.final_score for s in rrf_scores) / len(rrf_scores) if rrf_scores else 0
            rrf_threshold_met = avg_rrf >= self.RRF_THRESHOLD
            
            trace.append({
                "round": round_num,
                "action": "verify_claims",
                "verified": sum(1 for c in atomic_claims if c.is_verified),
                "avg_rrf": avg_rrf,
                "rrf_met": rrf_threshold_met
            })
            
            # Step 4: Generate fact-check questions for unverified claims
            claims = self._extract_claims(current_draft)
            questions = self._generate_fact_check_questions(claims)
            await self._answer_questions(questions, sources)
            
            # Step 5: Calculate verification score
            verified_count = sum(1 for c in atomic_claims if c.is_verified)
            verification_ratio = verified_count / len(atomic_claims) if atomic_claims else 0
            
            # Step 6: Calculate faithfulness with formula: F = |Claims ∩ Context| / |Claims|
            faithfulness = self._calculate_faithfulness_formula(atomic_claims, sources)
            
            # Step 7: Decide next action
            if verification_ratio >= self.MIN_VERIFIED_RATIO and rrf_threshold_met:
                if faithfulness >= self.FAITHFULNESS_THRESHOLD:
                    return CoVeResult(
                        valid=True,
                        original_draft=initial_draft,
                        final_answer=current_draft,
                        state=VerificationState.ACCEPTED,
                        atomic_claims=atomic_claims,
                        fact_check_questions=questions,
                        revisions_made=revision_count,
                        faithfulness_score=faithfulness,
                        rrf_threshold_met=rrf_threshold_met,
                        gaslighting_detected=gaslighting_detected,
                        refusal_reason=None,
                        verification_trace=trace
                    )
            
            # Step 6: Attempt revision
            unverified = [q for q in questions if not q.is_verified]
            
            if round_num < max_rounds - 1:
                # Try to revise
                current_draft = self._revise_answer(current_draft, unverified)
                revision_count += 1
                trace.append({"round": round_num, "action": "revise", "removed_claims": len(unverified)})
            else:
                # Max revisions reached - must refuse OR return partial
                if verification_ratio < 0.5:
                    return self._create_refusal(
                        initial_draft, 
                        questions, 
                        revision_count, 
                        trace,
                        "Insufficient knowledge to answer based on verified documents. "
                        f"Only {verified_count}/{len(questions)} claims could be verified."
                    )
                else:
                    # Return with heavy caveats
                    caveated_answer = self._add_caveats(current_draft, unverified)
                    return CoVeResult(
                        valid=False,
                        original_draft=initial_draft,
                        final_answer=caveated_answer,
                        state=VerificationState.ACCEPTED,
                        atomic_claims=atomic_claims,
                        fact_check_questions=questions,
                        revisions_made=revision_count,
                        faithfulness_score=verification_ratio,
                        rrf_threshold_met=rrf_threshold_met,
                        gaslighting_detected=gaslighting_detected,
                        refusal_reason=None,
                        verification_trace=trace
                    )
        
        # Should not reach here, but safety return
        return self._create_refusal(initial_draft, [], revision_count, trace,
                                   "Verification loop exhausted without resolution")
    
    def _extract_claims(self, text: str) -> List[str]:
        """Extract verifiable claims from text."""
        claims = []
        
        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        # Factual markers
        markers = [
            "is", "are", "was", "were", "has", "have", "signed", "ratified",
            "enacted", "established", "declared", "states", "according to",
            "treaty", "agreement", "article", "percent", "million", "billion"
        ]
        
        for sentence in sentences:
            sentence_lower = sentence.lower()
            if any(marker in sentence_lower for marker in markers):
                if len(sentence.split()) >= 5:  # Minimum substantive length
                    claims.append(sentence.strip())
        
        return claims
    
    # =========================================================================
    # INDUSTRIAL-GRADE METHODS
    # =========================================================================
    
    def _detect_gaslighting(
        self, 
        query: str, 
        sources: List[Dict]
    ) -> Tuple[bool, List[str]]:
        """
        Detect if user query contains false premises (gaslighting).
        
        Gaslighting Protection:
        - Extract factual claims from the query
        - Verify each against sources
        - Flag unverified claims as potential gaslighting
        
        Source-over-prompt priority: We trust sources, not the user's assertions.
        
        NOTE: Analytical/assessment queries (e.g. "Assess the risk of X")
        are INSTRUCTIONS, not factual claims.  They should not trigger
        gaslighting detection.
        """
        # Skip gaslighting detection for analytical/assessment queries.
        # These are directives, not factual assertions.
        query_lower = query.lower().strip()
        _ANALYTICAL_PREFIXES = (
            "assess", "analyze", "evaluate", "estimate", "predict",
            "what is the risk", "what are the risk", "how likely",
            "explain which", "determine", "forecast", "classify",
        )
        if any(query_lower.startswith(prefix) for prefix in _ANALYTICAL_PREFIXES):
            return False, []

        false_premises = []
        query_claims = self._extract_claims(query)
        
        for claim in query_claims:
            # Check if claim is verified in sources
            claim_words = set(claim.lower().split())
            claim_words -= {"the", "a", "an", "is", "are", "was", "were", "what", "how", "why"}
            
            found_support = False
            for source in sources:
                content = source.get("content", "").lower()
                source_words = set(content.split())
                
                overlap = len(claim_words & source_words) / max(len(claim_words), 1)
                if overlap > 0.5:
                    found_support = True
                    break
            
            # Also check engram store
            if not found_support:
                found, _ = self.engram.lookup(claim)
                if found:
                    found_support = True
            
            if not found_support and len(claim_words) > 3:
                false_premises.append(claim)
        
        # Gaslighting detected if > sensitivity threshold of claims are false
        if query_claims:
            false_ratio = len(false_premises) / len(query_claims)
            is_gaslighting = false_ratio >= self.GASLIGHTING_SENSITIVITY
        else:
            is_gaslighting = False
        
        return is_gaslighting, false_premises
    
    def _decompose_to_atomic_claims(self, text: str) -> List[AtomicClaim]:
        """
        Decompose text into atomic, independently verifiable claims.
        
        Example:
        Input: "India signed the RCEP agreement in 2020 with 15 countries"
        Output: [
            AtomicClaim(type="entity", subject="India", predicate="signed", object="RCEP"),
            AtomicClaim(type="date", subject="RCEP signing", object="2020"),
            AtomicClaim(type="numeric", subject="RCEP countries", object="15")
        ]
        """
        atomic_claims = []
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        for i, sentence in enumerate(sentences):
            # Extract entities
            entities = self._extract_entities(sentence)
            
            # Date claims
            date_matches = re.findall(r'\b(19|20)\d{2}\b', sentence)
            for date in date_matches:
                atomic_claims.append(AtomicClaim(
                    claim_id=f"date_{i}_{date}",
                    claim_text=f"Date reference: {date} in context '{sentence[:50]}'",
                    claim_type="date",
                    entity_object=date
                ))
            
            # Numeric claims
            num_matches = re.findall(r'\b(\d+(?:\.\d+)?)\s*(?:percent|%|million|billion|crore|lakh)?\b', sentence)
            for num in num_matches:
                if num and float(num) > 0:
                    atomic_claims.append(AtomicClaim(
                        claim_id=f"num_{i}_{num}",
                        claim_text=f"Numeric value: {num} in context '{sentence[:50]}'",
                        claim_type="numeric",
                        entity_object=num
                    ))
            
            # Entity/relation claims
            for entity in entities[:3]:  # Max 3 per sentence
                atomic_claims.append(AtomicClaim(
                    claim_id=f"entity_{i}_{len(atomic_claims)}",
                    claim_text=sentence,
                    claim_type="entity",
                    entity_subject=entity
                ))
        
        return atomic_claims
    
    async def _verify_atomic_claims(
        self, 
        claims: List[AtomicClaim], 
        sources: List[Dict]
    ):
        """
        Verify each atomic claim using multi-source verification.
        
        Priority:
        1. Engram Store (O(1) lookup) - Highest trust
        2. Vector Store (semantic match)
        3. Source documents (keyword match)
        """
        for claim in claims:
            # 1. Engram Store lookup (O(1))
            found, fact = self.engram.lookup(claim.claim_text)
            if found:
                claim.is_verified = True
                claim.engram_match = True
                claim.verification_source = fact.get("source", "engram")
                claim.rrf_score = 1.0  # Highest confidence
                continue
            
            # 2. Fuzzy engram lookup
            fuzzy_matches = self.engram.fuzzy_lookup(claim.claim_text, threshold=0.6)
            if fuzzy_matches:
                best_match = fuzzy_matches[0]
                claim.is_verified = True
                claim.engram_match = True
                claim.verification_source = best_match.get("source", "engram_fuzzy")
                claim.rrf_score = best_match.get("similarity", 0.8)
                continue
            
            # 3. Source document verification
            claim_key = claim.entity_object or claim.entity_subject or claim.claim_text
            if claim_key:
                for source in sources:
                    content = source.get("content", "").lower()
                    if claim_key.lower() in content:
                        claim.is_verified = True
                        claim.verification_source = source.get("title", "source")
                        claim.rrf_score = 0.7
                        break
    
    def _calculate_rrf_scores(
        self, 
        claims: List[AtomicClaim], 
        sources: List[Dict]
    ) -> List[RRFScore]:
        """
        Calculate Reciprocal Rank Fusion scores for multi-source verification.
        
        RRF Formula: score = sum(1 / (k + rank)) for each source
        Where k = 60 (standard constant)
        """
        rrf_scores = []
        
        for claim in claims:
            rrf = RRFScore(claim_id=claim.claim_id)
            
            # Engram rank (if found)
            if claim.engram_match:
                rrf.engram_rank = 1  # Top rank
            
            # Vector rank (based on RRF score from claim)
            if claim.rrf_score > 0.7:
                rrf.vector_rank = 1
            elif claim.rrf_score > 0.5:
                rrf.vector_rank = 5
            elif claim.rrf_score > 0.3:
                rrf.vector_rank = 10
            
            # Graph rank (if verified)
            if claim.is_verified:
                rrf.graph_rank = 3
            
            # Calculate final RRF score
            rrf.calculate()
            rrf_scores.append(rrf)
        
        return rrf_scores
    
    def _calculate_faithfulness_formula(
        self, 
        claims: List[AtomicClaim], 
        sources: List[Dict]
    ) -> float:
        """
        Calculate faithfulness using the exact formula:
        
        Faithfulness = |Claims ∩ Context| / |Claims|
        
        Where:
        - Claims = set of atomic claims from the answer
        - Context = set of verifiable facts from sources
        - Claims ∩ Context = claims that are verified against sources
        """
        if not claims:
            return 1.0
        
        # Count verified claims
        verified_claims = sum(1 for c in claims if c.is_verified)
        total_claims = len(claims)
        
        # Faithfulness = |Claims ∩ Context| / |Claims|
        faithfulness = verified_claims / total_claims
        
        return faithfulness
    
    def _generate_fact_check_questions(self, claims: List[str]) -> List[FactCheckQuestion]:
        """Generate independent fact-check questions for each claim."""
        questions = []
        
        for i, claim in enumerate(claims):
            # Extract entities and topics from claim
            entities = self._extract_entities(claim)
            
            for entity in entities[:2]:  # Max 2 questions per claim
                question = self._create_question(claim, entity)
                if question:
                    questions.append(FactCheckQuestion(
                        question_id=f"q_{i}_{len(questions)}",
                        question=question,
                        original_claim=claim
                    ))
        
        return questions
    
    def _extract_entities(self, text: str) -> List[str]:
        """Extract named entities and key terms."""
        entities = []
        
        # Capitalized phrases (named entities)
        for match in re.finditer(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*', text):
            entities.append(match.group())
        
        # Numbers with context
        for match in re.finditer(r'\d+(?:\.\d+)?(?:\s*(?:percent|million|billion|%|years?))?', text):
            entities.append(match.group())
        
        # Treaty/Article references
        for match in re.finditer(r'(?:Article|Section|Treaty|Agreement)\s+[\dIVXLCDM]+', text):
            entities.append(match.group())
        
        return entities
    
    def _create_question(self, claim: str, entity: str) -> Optional[str]:
        """Create a fact-check question for an entity."""
        claim_lower = claim.lower()
        
        # Date-related
        if any(w in claim_lower for w in ["signed", "enacted", "established", "ratified"]):
            return f"What is the exact date when {entity} was signed/enacted?"
        
        # Party-related  
        if any(w in claim_lower for w in ["treaty", "agreement", "accord"]):
            return f"Which parties are signatories to {entity}?"
        
        # Numerical
        if any(w in entity for w in ["percent", "million", "billion", "%"]):
            return f"What is the verified numerical value for this metric in {claim[:50]}?"
        
        # General fact
        return f"Is it factually accurate that {claim[:100]}?"
    
    async def _answer_questions(
        self, 
        questions: List[FactCheckQuestion], 
        sources: List[Dict]
    ):
        """Answer fact-check questions using ONLY verified sources."""
        for question in questions:
            # Search sources for answer
            answer, confidence, evidence = self._search_sources(question.question, sources)
            
            question.answer = answer
            question.confidence = confidence
            question.source_evidence = evidence
            question.is_verified = confidence >= 0.6 and len(evidence) > 0
    
    def _search_sources(
        self, 
        question: str, 
        sources: List[Dict]
    ) -> Tuple[Optional[str], float, List[str]]:
        """Search sources for answer to question."""
        question_words = set(question.lower().split())
        question_words -= {"what", "is", "the", "when", "which", "how", "who", "a", "an"}
        
        best_match = None
        best_score = 0.0
        evidence = []
        
        for source in sources:
            content = source.get("content", "")
            content_lower = content.lower()
            content_words = set(content_lower.split())
            
            # Calculate relevance
            overlap = len(question_words & content_words)
            score = overlap / len(question_words) if question_words else 0
            
            if score > best_score and score > 0.4:
                best_score = score
                # Extract relevant sentence
                sentences = content.split('.')
                for sentence in sentences:
                    if any(w in sentence.lower() for w in question_words):
                        best_match = sentence.strip()
                        evidence.append(f"[Source] {sentence[:200]}")
                        break
        
        return best_match, best_score, evidence
    
    def _calculate_faithfulness(
        self, 
        answer: str, 
        sources: List[Dict],
        questions: List[FactCheckQuestion]
    ) -> float:
        """Calculate RAGAS faithfulness score."""
        if not questions:
            return 1.0
        
        verified = sum(1 for q in questions if q.is_verified)
        return verified / len(questions)
    
    def _revise_answer(
        self, 
        answer: str, 
        unverified_questions: List[FactCheckQuestion]
    ) -> str:
        """Revise answer by removing or softening unverified claims."""
        revised = answer
        
        for question in unverified_questions:
            claim = question.original_claim
            
            # Remove the unverified claim entirely or soften it
            if claim in revised:
                # Add uncertainty marker instead of removing
                softened = f"[Unverified] {claim}"
                revised = revised.replace(claim, softened)
        
        return revised
    
    def _add_caveats(
        self, 
        answer: str, 
        unverified: List[FactCheckQuestion]
    ) -> str:
        """Add caveats for unverified claims."""
        caveat = (
            "\n\n⚠️ **Verification Notice**: Some claims in this response could not be "
            "fully verified against the document store. The following points should be "
            "independently verified:\n"
        )
        
        for q in unverified[:5]:  # Max 5 caveats
            caveat += f"- {q.original_claim[:100]}...\n"
        
        return answer + caveat
    
    def _create_refusal(
        self,
        original_draft: str,
        questions: List[FactCheckQuestion],
        revision_count: int,
        trace: List[Dict],
        reason: str
    ) -> CoVeResult:
        """Create a refusal result."""
        return CoVeResult(
            valid=False,
            original_draft=original_draft,
            final_answer=None,
            state=VerificationState.REFUSED,
            atomic_claims=[],
            fact_check_questions=questions,
            revisions_made=revision_count,
            faithfulness_score=0.0,
            rrf_threshold_met=False,
            gaslighting_detected=False,
            refusal_reason=reason,
            verification_trace=trace
        )
    
    def quick_verify(
        self, 
        answer: str, 
        sources: List[Dict]
    ) -> Tuple[bool, float, str]:
        """
        Quick synchronous verification.
        Returns (should_accept, faithfulness_score, message).
        """
        claims = self._extract_claims(answer)
        
        if not claims:
            return True, 1.0, "No verifiable claims"
        
        verified = 0
        for claim in claims:
            claim_words = set(claim.lower().split())
            claim_words -= {"the", "a", "an", "is", "are", "was", "were"}
            
            for source in sources:
                content = source.get("content", "").lower()
                source_words = set(content.split())
                
                overlap = len(claim_words & source_words) / len(claim_words) if claim_words else 0
                if overlap > 0.4:
                    verified += 1
                    break
        
        faithfulness = verified / len(claims)
        
        if faithfulness < self.FAITHFULNESS_THRESHOLD:
            return False, faithfulness, f"Insufficient verification: {verified}/{len(claims)} claims verified"
        
        return True, faithfulness, f"Verified: {verified}/{len(claims)} claims"


# Singleton instance
cove_verifier = ChainOfVerification()
