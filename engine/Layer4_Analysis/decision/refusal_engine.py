"""
Refusal & Uncertainty Manager - ICE Method Implementation
Implements threshold-based refusal logic to prevent model "bluffing".
ICE = Instructions, Constraints, Escalation
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import re


class RefusalReason(Enum):
    """Reasons for refusing to answer."""
    LOW_CONFIDENCE = "low_confidence"
    INSUFFICIENT_SOURCES = "insufficient_sources"
    CONTRADICTORY_SOURCES = "contradictory_sources"
    TEMPORAL_AMBIGUITY = "temporal_ambiguity"
    LOGICAL_WEAKNESS = "logical_weakness"
    OUTSIDE_KNOWLEDGE_DOMAIN = "outside_knowledge_domain"
    CLASSIFIED_TOPIC = "classified_topic"
    SPECULATION_REQUIRED = "speculation_required"


class EscalationLevel(Enum):
    """Escalation levels for uncertain answers."""
    NONE = 0
    WARNING = 1
    CAVEAT = 2
    PARTIAL_ANSWER = 3
    REFUSAL = 4


@dataclass
class ConfidenceAssessment:
    """Assessment of confidence in an answer."""
    overall_score: float  # 0.0 to 1.0
    retrieval_score: float  # RRF/hybrid score
    faithfulness_score: float  # RAGAS faithfulness
    source_coverage: float  # How well sources cover the query
    temporal_validity: float  # Temporal relevance
    
    escalation_level: EscalationLevel
    refusal_reason: Optional[RefusalReason]
    
    constraints_violated: List[str]
    warnings: List[str]
    logic_score: float = 1.0  # Causal/logical grounding quality
    
    def should_refuse(self) -> bool:
        return self.escalation_level == EscalationLevel.REFUSAL
    
    def needs_caveat(self) -> bool:
        return self.escalation_level in [EscalationLevel.CAVEAT, EscalationLevel.PARTIAL_ANSWER]


class RefusalEngine:
    """
    ICE-based Refusal Engine.
    Determines when to refuse, caveat, or escalate responses.
    """
    
    # Configurable thresholds (θ values)
    THRESHOLDS = {
        "min_retrieval_score": 0.35,      # Minimum RRF score to proceed
        "min_faithfulness_score": 0.50,    # Minimum RAGAS faithfulness
        "min_source_count": 2,             # Minimum sources required
        "max_contradiction_ratio": 0.30,   # Max allowed contradiction
        "min_temporal_validity": 0.40,     # Min temporal relevance
        "min_overall_confidence": 0.45,    # Overall threshold
        "min_logic_score": 0.35,           # Minimum causal/logical grounding
    }
    
    # Topics requiring special handling
    SENSITIVE_TOPICS = [
        "nuclear", "classified", "secret", "confidential",
        "intelligence", "espionage", "covert"
    ]
    
    # Topics outside domain
    OUT_OF_DOMAIN = [
        "medical advice", "legal counsel", "investment advice",
        "personal recommendation", "future prediction"
    ]
    
    def __init__(self, thresholds: Dict[str, float] = None):
        if thresholds:
            self.THRESHOLDS.update(thresholds)
        
        self._refusal_messages = {
            RefusalReason.LOW_CONFIDENCE: 
                "I don't have sufficient confidence to answer this query based on verified documents. "
                "The available evidence does not meet the required threshold for a reliable response.",
            
            RefusalReason.INSUFFICIENT_SOURCES:
                "Insufficient knowledge to answer this query. I found fewer than {min_sources} "
                "relevant sources in the verified document database.",
            
            RefusalReason.CONTRADICTORY_SOURCES:
                "The available sources contain contradictory information on this topic. "
                "I cannot provide a definitive answer without highlighting these conflicts.",
            
            RefusalReason.TEMPORAL_AMBIGUITY:
                "There is temporal ambiguity in the available information. Some sources may be "
                "outdated or superseded. Please specify the time period of interest.",

            RefusalReason.LOGICAL_WEAKNESS:
                "The explanation does not uniquely explain observed signals. "
                "Multiple alternative explanations fit the same evidence.",
            
            RefusalReason.OUTSIDE_KNOWLEDGE_DOMAIN:
                "This query falls outside my knowledge domain of diplomatic and geopolitical intelligence. "
                "I cannot provide reliable information on this topic.",
            
            RefusalReason.CLASSIFIED_TOPIC:
                "This query touches on topics that may involve classified or sensitive information. "
                "I can only provide analysis based on publicly available documents.",
            
            RefusalReason.SPECULATION_REQUIRED:
                "Answering this query would require speculation beyond the available evidence. "
                "I can only provide analysis grounded in verified documents."
        }
    
    def assess_confidence(
        self,
        query: str,
        sources: List[Dict],
        answer: str,
        retrieval_scores: List[float],
        faithfulness_score: float,
        temporal_conflicts: List[Dict] = None,
        logic_score: Optional[float] = None,
    ) -> ConfidenceAssessment:
        """
        Assess confidence in an answer using the ICE method.
        Returns a full confidence assessment with escalation level.
        """
        constraints_violated = []
        warnings = []
        
        # ===== INSTRUCTIONS: Check basic requirements =====
        
        # Check source count
        source_count = len(sources)
        if source_count < self.THRESHOLDS["min_source_count"]:
            constraints_violated.append(f"Only {source_count} sources found (min: {self.THRESHOLDS['min_source_count']})")
        
        # Check retrieval scores
        avg_retrieval = sum(retrieval_scores) / len(retrieval_scores) if retrieval_scores else 0
        if avg_retrieval < self.THRESHOLDS["min_retrieval_score"]:
            constraints_violated.append(f"Low retrieval relevance: {avg_retrieval:.2f}")
        
        # Check faithfulness
        if faithfulness_score < self.THRESHOLDS["min_faithfulness_score"]:
            constraints_violated.append(f"Low faithfulness score: {faithfulness_score:.2f}")

        # Check causal/logical grounding.
        try:
            resolved_logic_score = max(0.0, min(1.0, float(logic_score if logic_score is not None else 1.0)))
        except Exception:
            resolved_logic_score = 0.0
        if resolved_logic_score < self.THRESHOLDS["min_logic_score"]:
            constraints_violated.append(
                "Explanation does not uniquely explain observed signals "
                f"(logic_score={resolved_logic_score:.2f})"
            )
        
        # ===== CONSTRAINTS: Check domain and sensitivity =====
        
        query_lower = query.lower()
        
        # Check sensitive topics
        for topic in self.SENSITIVE_TOPICS:
            if topic in query_lower:
                warnings.append(f"Query touches sensitive topic: {topic}")
        
        # Check out-of-domain
        for domain in self.OUT_OF_DOMAIN:
            if domain in query_lower:
                return ConfidenceAssessment(
                    overall_score=0.0,
                    retrieval_score=avg_retrieval,
                    faithfulness_score=faithfulness_score,
                    source_coverage=source_count / 10,
                    temporal_validity=1.0,
                    logic_score=resolved_logic_score,
                    escalation_level=EscalationLevel.REFUSAL,
                    refusal_reason=RefusalReason.OUTSIDE_KNOWLEDGE_DOMAIN,
                    constraints_violated=[f"Query outside domain: {domain}"],
                    warnings=[]
                )
        
        # Check for contradictions
        contradiction_ratio = self._detect_contradiction_ratio(sources)
        if contradiction_ratio > self.THRESHOLDS["max_contradiction_ratio"]:
            warnings.append(f"High contradiction ratio: {contradiction_ratio:.2f}")
        
        # Check temporal validity
        temporal_validity = 1.0
        if temporal_conflicts:
            temporal_validity = max(0, 1.0 - (len(temporal_conflicts) * 0.2))
            if temporal_validity < self.THRESHOLDS["min_temporal_validity"]:
                warnings.append(f"Temporal conflicts detected: {len(temporal_conflicts)}")
        
        # ===== ESCALATION: Determine response level =====
        
        # Calculate overall score
        source_coverage = min(1.0, source_count / 10)
        overall_score = (
            avg_retrieval * 0.25 +
            faithfulness_score * 0.35 +
            source_coverage * 0.20 +
            temporal_validity * 0.20
        )
        # Apply a deterministic damping factor from logical grounding quality.
        overall_score *= (0.5 + (0.5 * resolved_logic_score))
        
        # Determine escalation level
        if resolved_logic_score < self.THRESHOLDS["min_logic_score"]:
            escalation = EscalationLevel.REFUSAL
            reason = RefusalReason.LOGICAL_WEAKNESS
        elif len(constraints_violated) >= 3 or overall_score < 0.3:
            escalation = EscalationLevel.REFUSAL
            reason = self._determine_refusal_reason(constraints_violated, warnings)
        elif overall_score < self.THRESHOLDS["min_overall_confidence"]:
            escalation = EscalationLevel.PARTIAL_ANSWER
            reason = None
        elif len(warnings) >= 2 or overall_score < 0.6:
            escalation = EscalationLevel.CAVEAT
            reason = None
        elif len(warnings) >= 1:
            escalation = EscalationLevel.WARNING
            reason = None
        else:
            escalation = EscalationLevel.NONE
            reason = None
        
        return ConfidenceAssessment(
            overall_score=overall_score,
            retrieval_score=avg_retrieval,
            faithfulness_score=faithfulness_score,
            source_coverage=source_coverage,
            temporal_validity=temporal_validity,
            logic_score=resolved_logic_score,
            escalation_level=escalation,
            refusal_reason=reason,
            constraints_violated=constraints_violated,
            warnings=warnings
        )
    
    def _detect_contradiction_ratio(self, sources: List[Dict]) -> float:
        """Detect ratio of contradictory statements in sources."""
        if len(sources) < 2:
            return 0.0
        
        # Simple heuristic: look for negation patterns
        negation_patterns = [
            r"\bnot\b", r"\bnever\b", r"\bdenied\b", r"\brejected\b",
            r"\bhowever\b", r"\bcontrary\b", r"\bopposed\b"
        ]
        
        contradiction_count = 0
        for src in sources:
            content = src.get("content", "").lower()
            for pattern in negation_patterns:
                if re.search(pattern, content):
                    contradiction_count += 1
                    break
        
        return contradiction_count / len(sources)
    
    def _determine_refusal_reason(
        self, 
        constraints: List[str], 
        warnings: List[str]
    ) -> RefusalReason:
        """Determine the primary refusal reason."""
        constraints_text = " ".join(constraints).lower()
        warnings_text = " ".join(warnings).lower()
        
        if "source" in constraints_text:
            return RefusalReason.INSUFFICIENT_SOURCES
        if "uniquely explain observed signals" in constraints_text or "logic_score" in constraints_text:
            return RefusalReason.LOGICAL_WEAKNESS
        if "contradiction" in warnings_text:
            return RefusalReason.CONTRADICTORY_SOURCES
        if "temporal" in warnings_text:
            return RefusalReason.TEMPORAL_AMBIGUITY
        if "sensitive" in warnings_text:
            return RefusalReason.CLASSIFIED_TOPIC
        
        return RefusalReason.LOW_CONFIDENCE
    
    def format_response(
        self, 
        assessment: ConfidenceAssessment,
        original_answer: str = None
    ) -> Dict[str, Any]:
        """
        Format the response based on confidence assessment.
        May refuse, add caveats, or return as-is.
        """
        if assessment.should_refuse():
            message = self._refusal_messages.get(
                assessment.refusal_reason,
                self._refusal_messages[RefusalReason.LOW_CONFIDENCE]
            )
            
            return {
                "type": "refusal",
                "answer": None,
                "message": message.format(min_sources=self.THRESHOLDS["min_source_count"]),
                "confidence": assessment.overall_score,
                "reason": assessment.refusal_reason.value if assessment.refusal_reason else None,
                "constraints_violated": assessment.constraints_violated,
                "suggestion": "Please refine your query or provide additional context."
            }
        
        if assessment.needs_caveat():
            caveats = []
            
            if assessment.escalation_level == EscalationLevel.PARTIAL_ANSWER:
                caveats.append("⚠️ **Partial Answer**: This response is based on limited evidence.")
            
            if assessment.temporal_validity < 0.7:
                caveats.append("📅 **Temporal Note**: Some sources may be dated. Please verify current status.")
            
            if assessment.source_coverage < 0.5:
                caveats.append("📚 **Limited Sources**: This answer is based on a limited set of documents.")
            
            for warning in assessment.warnings:
                caveats.append(f"ℹ️ {warning}")
            
            caveat_text = "\n".join(caveats)
            
            return {
                "type": "caveat",
                "answer": f"{caveat_text}\n\n---\n\n{original_answer}" if original_answer else None,
                "caveats": caveats,
                "confidence": assessment.overall_score,
                "warnings": assessment.warnings
            }
        
        # Normal response with optional warning
        result = {
            "type": "normal",
            "answer": original_answer,
            "confidence": assessment.overall_score
        }
        
        if assessment.escalation_level == EscalationLevel.WARNING:
            result["warnings"] = assessment.warnings
        
        return result
    
    def get_refusal_message(self, reason: RefusalReason, **kwargs) -> str:
        """Get formatted refusal message."""
        message = self._refusal_messages.get(reason, self._refusal_messages[RefusalReason.LOW_CONFIDENCE])
        return message.format(**kwargs)


# Singleton instance
refusal_engine = RefusalEngine()
