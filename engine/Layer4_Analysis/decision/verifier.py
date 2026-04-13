"""
Groundedness Scoring & Verification Agent
Implements RAGAS-style faithfulness metrics and claim verification.
"""

from typing import List, Dict, Any, Tuple, Set
from dataclasses import dataclass, field
import re
from Config.thresholds import SignalThresholds
from engine.Layer4_Analysis.evidence.signal_ontology import canonicalize_signal_token
from engine.Layer4_Analysis.decision.causal_verifier import (
    causal_support,
    exclusivity_score,
    logical_verification as _logical_verification,
    logical_verification_details as _logical_verification_details,
)


@dataclass
class Claim:
    """A claim extracted from an answer."""
    claim_id: str
    text: str
    confidence: float
    source_sentence: str
    is_grounded: bool = False
    supporting_sources: List[int] = field(default_factory=list)


@dataclass
class VerificationResult:
    """Result of verifying an answer against sources."""
    answer: str
    total_claims: int
    grounded_claims: int
    ungrounded_claims: int
    faithfulness_score: float
    claim_details: List[Claim]
    source_coverage: float
    verification_notes: List[str]


class Verifier:
    """
    Verifies claims against source documents and grounds hypotheses in StateContext.
    """
    HARD_SIGNALS = {
        "high_mobilization",
        "logistics_buildup",
        "border_positioning",
        "sanctions_pressure",
        "SIG_MIL_MOBILIZATION",
        "SIG_MIL_LOGISTICS_SURGE",
        "SIG_MIL_FORWARD_DEPLOYMENT",
        "SIG_ECO_SANCTIONS_ACTIVE",
    }

    DEFAULT_REQUIREMENTS = {
        # Military
        "high_mobilization": SignalThresholds.HIGH_MOBILIZATION,
        "logistics_buildup": SignalThresholds.HIGH_LOGISTICS_ACTIVITY,
        "border_positioning": 0.60,
        "recent_exercises": SignalThresholds.SIGNIFICANT_EXERCISES,
        "SIG_MIL_MOBILIZATION": SignalThresholds.HIGH_MOBILIZATION,
        "SIG_MIL_LOGISTICS_SURGE": SignalThresholds.HIGH_LOGISTICS_ACTIVITY,
        "SIG_MIL_FORWARD_DEPLOYMENT": 0.60,
        "SIG_MIL_EXERCISE_ESCALATION": SignalThresholds.SIGNIFICANT_EXERCISES,
        "SIG_MIL_BORDER_CLASHES": 0.40,
        
        # Diplomatic
        "hostility_tone_high": SignalThresholds.HIGH_HOSTILITY_TONE,
        "negotiation_channels_open": SignalThresholds.NEGOTIATION_OPEN,
        "alliance_activity_high": SignalThresholds.HIGH_ALLIANCE_ACTIVITY,
        "alliance_realignment": SignalThresholds.ALLIANCE_REALIGNMENT,
        "escalation_ladder_active": 0.55,
        "SIG_DIP_HOSTILE_RHETORIC": SignalThresholds.HIGH_HOSTILITY_TONE,
        "SIG_DIP_CHANNEL_OPEN": SignalThresholds.NEGOTIATION_OPEN,
        "SIG_DIP_CHANNEL_CLOSURE": 0.50,
        "SIG_DIP_DEESCALATION": 0.40,
        "SIG_DIP_ALLIANCE_COORDINATION": SignalThresholds.HIGH_ALLIANCE_ACTIVITY,
        
        # Economic
        "sanctions_pressure": SignalThresholds.HIGH_SANCTIONS_PRESSURE,
        "economic_pressure_high": SignalThresholds.HIGH_ECONOMIC_PRESSURE,
        "trade_dependency_high": SignalThresholds.HIGH_TRADE_DEPENDENCY,
        "SIG_ECO_SANCTIONS_ACTIVE": SignalThresholds.HIGH_SANCTIONS_PRESSURE,
        "SIG_ECO_PRESSURE_HIGH": SignalThresholds.HIGH_ECONOMIC_PRESSURE,
        "SIG_ECO_TRADE_LEVERAGE": SignalThresholds.HIGH_TRADE_DEPENDENCY,
        
        # Domestic / Political
        "regime_instability": SignalThresholds.REGIME_INSTABILITY,
        "civil_unrest": SignalThresholds.HIGH_CIVIL_UNREST,
        "protest_pressure": SignalThresholds.HIGH_PROTEST_PRESSURE,
        "SIG_DOM_REGIME_INSTABILITY": SignalThresholds.REGIME_INSTABILITY,
        "SIG_DOM_CIVIL_UNREST": SignalThresholds.HIGH_CIVIL_UNREST,
        "SIG_DOM_PROTEST_PRESSURE": SignalThresholds.HIGH_PROTEST_PRESSURE,

        # Capability
        "SIG_CAP_SUPPLY_STOCKPILING": 0.60,
        "SIG_CAP_CYBER_PREPARATION": 0.60,
        "SIG_CAP_EVACUATION_ACTIVITY": 0.60,
    }

    HARD_EVIDENCE_MIN_SUPPORT = 0.50
    
    # Docstring moved to init or class to avoid floating string issues
    
    def __init__(self, llm_client=None):
        self.llm = llm_client
        
        # Claim extraction patterns
        self._claim_patterns = [
            r"([A-Z][^.!?]*(?:is|are|was|were|has|have|will|would|should|could|can|may|must)[^.!?]*[.!?])",
            r"([A-Z][^.!?]*(?:stated|declared|announced|signed|ratified|enacted)[^.!?]*[.!?])",
            r"([A-Z][^.!?]*(?:Article|Section|Treaty|Agreement|Convention)[^.!?]*[.!?])"
        ]
    
    def extract_claims(self, answer: str) -> List[Claim]:
        """Extract verifiable claims from an answer."""
        claims = []
        claim_id = 0
        
        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', answer)
        
        for sentence in sentences:
            # Skip short sentences
            if len(sentence.split()) < 5:
                continue
            
            # Check if sentence contains a claim
            is_claim = False
            for pattern in self._claim_patterns:
                if re.search(pattern, sentence):
                    is_claim = True
                    break
            
            if is_claim or self._contains_factual_assertion(sentence):
                claims.append(Claim(
                    claim_id=f"claim_{claim_id}",
                    text=sentence.strip(),
                    confidence=0.0,
                    source_sentence=sentence,
                    supporting_sources=[]
                ))
                claim_id += 1
        
        return claims
    
    def _contains_factual_assertion(self, sentence: str) -> bool:
        """Check if sentence contains a factual assertion."""
        factual_markers = [
            "according to", "treaty", "agreement", "signed", "ratified",
            "established", "declares", "affirms", "recognizes", "percent",
            "million", "billion", "article", "section", "in force"
        ]
        sentence_lower = sentence.lower()
        return any(marker in sentence_lower for marker in factual_markers)
    
    def verify_claim_against_sources(
        self, 
        claim: Claim, 
        sources: List[Dict]
    ) -> Tuple[bool, float, List[int]]:
        """
        Verify a single claim against signal provenance metadata.

        BOUNDARY CONTRACT: Layer-4 must not read raw document content.
        Instead of word-overlap against document text, we verify claims
        by matching key phrases / entity references against structured
        signal metadata (signal tokens, source names, provenance summaries).

        Returns (is_grounded, confidence, supporting_source_indices).
        """
        supporting = []
        max_similarity = 0.0
        
        # Extract key entities/phrases from the claim
        key_phrases = self._extract_key_phrases(claim.text)
        claim_words = set(claim.text.lower().split())
        claim_words -= {"the", "a", "an", "is", "are", "was", "were", "has", "have"}
        
        for i, source in enumerate(sources):
            # Build a metadata-only text from signal provenance fields
            # NEVER read source.get("content") — that's raw document text
            signal_token = str(source.get("signal", source.get("signal_token", ""))).strip()
            source_name = str(source.get("source", source.get("source_name", ""))).strip()
            provenance_summary = str(source.get("provenance_summary", source.get("excerpt", ""))).strip()
            
            # Compose a structured reference string from metadata
            metadata_text = f"{signal_token} {source_name} {provenance_summary}".lower()
            metadata_words = set(metadata_text.split())
            
            # Calculate word overlap against metadata (not document content)
            overlap = len(claim_words & metadata_words)
            similarity = overlap / len(claim_words) if claim_words else 0
            
            if similarity > 0.3:  # Lower threshold since we're matching metadata
                supporting.append(i)
                max_similarity = max(max_similarity, similarity)
            
            # Check for key phrases in metadata
            for phrase in key_phrases:
                if phrase.lower() in metadata_text:
                    if i not in supporting:
                        supporting.append(i)
                    max_similarity = max(max_similarity, 0.7)
        
        is_grounded = len(supporting) > 0 and max_similarity > 0.3
        
        return is_grounded, max_similarity, supporting
    
    def _extract_key_phrases(self, text: str) -> List[str]:
        """Extract key phrases from text."""
        phrases = []
        
        # Named entities (capitalized sequences)
        for match in re.finditer(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*", text):
            phrases.append(match.group())
        
        # Numbers and dates
        for match in re.finditer(r"\d+(?:\.\d+)?(?:\s*(?:percent|million|billion))?", text):
            phrases.append(match.group())
        
        # Treaty/Article references
        for match in re.finditer(r"(?:Article|Section|Treaty)\s+\d+", text):
            phrases.append(match.group())
        
        return phrases
    
    def verify_answer(
        self, 
        answer: str, 
        sources: List[Dict]
    ) -> VerificationResult:
        """
        Fully verify an answer against sources.
        Returns comprehensive verification result.
        """
        # Extract claims
        claims = self.extract_claims(answer)
        
        if not claims:
            return VerificationResult(
                answer=answer,
                total_claims=0,
                grounded_claims=0,
                ungrounded_claims=0,
                faithfulness_score=1.0,  # No claims = nothing to verify
                claim_details=[],
                source_coverage=0.0,
                verification_notes=["No verifiable claims extracted"]
            )
        
        # Verify each claim
        grounded_count = 0
        sources_used: Set[int] = set()
        verification_notes = []
        
        for claim in claims:
            is_grounded, confidence, supporting = self.verify_claim_against_sources(claim, sources)
            
            claim.is_grounded = is_grounded
            claim.confidence = confidence
            claim.supporting_sources = supporting
            
            if is_grounded:
                grounded_count += 1
                sources_used.update(supporting)
            else:
                verification_notes.append(f"Ungrounded: {claim.text[:50]}...")
        
        # Calculate metrics
        faithfulness = grounded_count / len(claims) if claims else 0.0
        source_coverage = len(sources_used) / len(sources) if sources else 0.0
        
        return VerificationResult(
            answer=answer,
            total_claims=len(claims),
            grounded_claims=grounded_count,
            ungrounded_claims=len(claims) - grounded_count,
            faithfulness_score=faithfulness,
            claim_details=claims,
            source_coverage=source_coverage,
            verification_notes=verification_notes
        )

    def verify_hypothesis_grounding(
        self,
        hypothesis_details: Dict[str, Any],
        state_context: Any,
    ) -> Dict[str, Any]:
        """
        Verify hypothesis signal claims against StateContext contract.
        """
        details = dict(hypothesis_details or {})
        predicted = [str(item) for item in list(details.get("predicted_signals", []) or []) if str(item).strip()]
        matched = [str(item) for item in list(details.get("matched_signals", []) or []) if str(item).strip()]

        grounded_signals: List[str] = []
        unsupported_signals: List[str] = []
        scores: Dict[str, float] = {}
        for signal in predicted:
            evidence_score = verify_signal_support(state_context, signal)
            score = evidence_score if evidence_score > 0.0 else self._state_signal_score(state_context, signal)
            scores[signal] = score
            if signal in matched:
                if score >= self._signal_threshold(signal):
                    grounded_signals.append(signal)
                else:
                    unsupported_signals.append(signal)

        total_predicted = len(predicted)
        grounding_score = (len(grounded_signals) / total_predicted) if total_predicted else 0.0
        hard_predicted = [signal for signal in predicted if signal in self.HARD_SIGNALS]
        hard_grounded = [signal for signal in grounded_signals if signal in self.HARD_SIGNALS]
        hard_unsupported = [signal for signal in unsupported_signals if signal in self.HARD_SIGNALS]
        hard_support = (len(hard_grounded) / len(hard_predicted)) if hard_predicted else 1.0
        hard_evidence_required = len(hard_predicted) > 0
        hard_pass = (hard_support >= self.HARD_EVIDENCE_MIN_SUPPORT) if hard_evidence_required else True

        return {
            "total_predicted_signals": total_predicted,
            "claimed_matched_signals": len(matched),
            "grounded_signals": len(grounded_signals),
            "grounding_score": grounding_score,
            "unsupported_signals": unsupported_signals,
            "signal_scores": scores,
            "hard_predicted_count": len(hard_predicted),
            "hard_grounded_count": len(hard_grounded),
            "hard_unsupported_signals": hard_unsupported,
            "hard_evidence_support": hard_support,
            "hard_evidence_required": hard_evidence_required,
            "hard_evidence_threshold": self.HARD_EVIDENCE_MIN_SUPPORT,
            "hard_evidence_pass": hard_pass,
        }

    def _state_signal_score(self, state_context: Any, signal: str) -> float:
        def state_value(path: str, default: float) -> float:
            current: Any = state_context
            for part in path.split("."):
                if isinstance(current, dict):
                    current = current.get(part)
                else:
                    current = getattr(current, part, None)
                if current is None:
                    return default
            if isinstance(current, bool):
                return 1.0 if current else 0.0
            if isinstance(current, str):
                token = current.strip().lower()
                if token in {"high", "active", "true", "yes"}:
                    return 1.0
                if token in {"medium", "moderate"}:
                    return 0.6
                if token in {"low", "inactive", "none", "false", "no"}:
                    return 0.0
            try:
                return float(current)
            except Exception:
                return default

        military_mobilization = state_value("military.mobilization_level", 0.0)
        military_clashes = state_value("military.clash_history", 0.0)
        military_exercises = state_value("military.exercises", 0.0)
        hostility = state_value("diplomatic.hostility_tone", 0.0)
        negotiations = state_value("diplomatic.negotiations", 0.0)
        alliances = state_value("diplomatic.alliances", 0.0)
        sanctions = state_value("economic.sanctions", 0.0)
        econ_pressure = state_value("economic.economic_pressure", 0.0)
        trade_dependency = state_value("economic.trade_dependency", 0.0)
        regime_stability = state_value("domestic.regime_stability", 0.5)
        unrest = state_value("domestic.unrest", 0.0)
        protests = state_value("domestic.protests", 0.0)

        scores = {
            "high_mobilization": military_mobilization,
            "logistics_buildup": min(1.0, (military_mobilization * 0.7) + (military_exercises / 20.0)),
            "border_positioning": max(military_mobilization, min(1.0, military_clashes / 10.0)),
            "recent_exercises": min(1.0, military_exercises / 10.0),
            "hostility_tone_high": hostility,
            "negotiation_channels_open": negotiations,
            "alliance_activity_high": alliances,
            "alliance_realignment": min(1.0, (alliances * 0.6) + (hostility * 0.4)),
            "escalation_ladder_active": min(1.0, ((military_exercises / 10.0) + hostility) / 2.0),
            "sanctions_pressure": sanctions,
            "economic_pressure_high": econ_pressure,
            "trade_dependency_high": trade_dependency,
            "regime_instability": max(0.0, 1.0 - regime_stability),
            "civil_unrest": unrest,
            "protest_pressure": protests,
            # Canonical signal ontology
            "SIG_MIL_MOBILIZATION": military_mobilization,
            "SIG_MIL_LOGISTICS_SURGE": min(1.0, (military_mobilization * 0.7) + (military_exercises / 20.0)),
            "SIG_MIL_FORWARD_DEPLOYMENT": max(military_mobilization, min(1.0, military_clashes / 10.0)),
            "SIG_MIL_EXERCISE_ESCALATION": min(1.0, military_exercises / 10.0),
            "SIG_MIL_BORDER_CLASHES": min(1.0, military_clashes / 5.0),
            "SIG_DIP_HOSTILE_RHETORIC": hostility,
            "SIG_DIP_CHANNEL_OPEN": negotiations,
            "SIG_DIP_CHANNEL_CLOSURE": max(0.0, 1.0 - negotiations),
            "SIG_DIP_DEESCALATION": max(0.0, min(1.0, (1.0 - hostility) * negotiations)),
            "SIG_DIP_ALLIANCE_COORDINATION": alliances,
            "SIG_ECO_SANCTIONS_ACTIVE": sanctions,
            "SIG_ECO_PRESSURE_HIGH": econ_pressure,
            "SIG_ECO_TRADE_LEVERAGE": trade_dependency,
            "SIG_DOM_REGIME_INSTABILITY": max(0.0, 1.0 - regime_stability),
            "SIG_DOM_CIVIL_UNREST": unrest,
            "SIG_DOM_PROTEST_PRESSURE": protests,
            "SIG_CAP_SUPPLY_STOCKPILING": 1.0 if state_value("capability.supply_stockpiling", 0.0) > 0.5 else 0.0,
            "SIG_CAP_CYBER_PREPARATION": 1.0 if state_value("capability.cyber_activity", 0.0) > 0.5 else 0.0,
            "SIG_CAP_EVACUATION_ACTIVITY": 1.0 if state_value("capability.evacuation_activity", 0.0) > 0.5 else 0.0,
        }
        raw = str(signal or "").strip()
        canonical = canonicalize_signal_token(raw) or raw.upper().replace("-", "_").replace(" ", "_")
        return float(scores.get(canonical, scores.get(raw, 0.0)))

    def _signal_threshold(self, signal: str) -> float:
        return float(self.DEFAULT_REQUIREMENTS.get(str(signal), 0.50))
    
    def get_faithfulness_score(
        self, 
        answer: str, 
        sources: List[Dict]
    ) -> Tuple[float, Dict]:
        """
        Quick faithfulness score calculation.
        RAGAS: (Claims intersection Context) / Total Claims
        """
        result = self.verify_answer(answer, sources)
        
        return result.faithfulness_score, {
            "total_claims": result.total_claims,
            "grounded_claims": result.grounded_claims,
            "source_coverage": result.source_coverage
        }


class FullVerifier:
    """
    Deterministic signal verifier:
    verifies only ontology tokens against StateContext.
    """

    @staticmethod
    def _normalize_signals(predicted_signals) -> List[str]:
        normalized: List[str] = []
        seen = set()
        for sig in list(predicted_signals or []):
            raw = str(sig or "").strip()
            if not raw:
                continue
            token = canonicalize_signal_token(raw) or raw.upper().replace("-", "_").replace(" ", "_")
            if token in seen:
                continue
            seen.add(token)
            normalized.append(token)
        return normalized

    def verify(self, predicted_signals, state_context) -> float:
        normalized = self._normalize_signals(predicted_signals)
        if not normalized:
            return 0.0
        # Deterministic verification from signal-linked evidence reliability.
        score = 0.0
        for token in normalized:
            score += verify_signal_support(state_context, token)
        return score / len(normalized)


def _resolve_signal_evidence(state_context: Any) -> Dict[str, List[Any]]:
    if isinstance(state_context, dict):
        payload = state_context.get("signal_evidence", {})
        if isinstance(payload, dict):
            return payload
        return {}
    payload = getattr(state_context, "signal_evidence", {})
    if isinstance(payload, dict):
        return payload
    return {}


def _resolve_signal_provenance(state_context: Any) -> Dict[str, List[Any]]:
    if isinstance(state_context, dict):
        evidence_ctx = state_context.get("evidence", {})
        if isinstance(evidence_ctx, dict):
            payload = evidence_ctx.get("signal_provenance", {})
            if isinstance(payload, dict):
                return payload
        return {}

    evidence_ctx = getattr(state_context, "evidence", None)
    payload = getattr(evidence_ctx, "signal_provenance", {}) if evidence_ctx else {}
    if isinstance(payload, dict):
        return payload
    return {}


def verify_signal_support(state_context: Any, signal: str) -> float:
    """
    Deterministic support score from signal-level evidence provenance.
    """
    token = canonicalize_signal_token(str(signal or "").strip()) or str(signal or "").strip().upper()
    if not token:
        return 0.0

    signal_evidence = _resolve_signal_evidence(state_context)
    rows = list(signal_evidence.get(token, []) or [])

    if not rows:
        signal_provenance = _resolve_signal_provenance(state_context)
        rows = list(signal_provenance.get(token, []) or [])

    if not rows:
        return 0.0

    reliabilities: List[float] = []
    for row in rows:
        if isinstance(row, dict):
            value = row.get("reliability", row.get("confidence", 0.0))
        else:
            value = getattr(row, "reliability", getattr(row, "confidence", 0.0))
        try:
            reliabilities.append(max(0.0, min(1.0, float(value or 0.0))))
        except Exception:
            continue

    if not reliabilities:
        return 0.0
    return sum(reliabilities) / len(reliabilities)


def logical_verification(session: Any) -> float:
    """
    Public compatibility wrapper for causal/logical grounding checks.
    """
    return float(_logical_verification(session))


def logical_verification_details(session: Any) -> Dict[str, Any]:
    """
    Public compatibility wrapper returning per-hypothesis logic diagnostics.
    """
    details = _logical_verification_details(session)
    if not isinstance(details, dict):
        return {"logic_score": 0.0, "hypothesis_scores": []}
    return details


def combine_verification_scores(cove_score: float, ragas_score: float, logic_score: float) -> float:
    """
    Combine textual grounding and logical grounding into a single score.

    Formula:
      verification = 0.6 * min(cove, ragas) + 0.4 * logic
    """
    try:
        cove = max(0.0, min(1.0, float(cove_score or 0.0)))
    except Exception:
        cove = 0.0
    try:
        ragas = max(0.0, min(1.0, float(ragas_score or 0.0)))
    except Exception:
        ragas = 0.0
    try:
        logic = max(0.0, min(1.0, float(logic_score or 0.0)))
    except Exception:
        logic = 0.0

    evidence = min(cove, ragas)
    return (0.6 * evidence) + (0.4 * logic)


# Singleton instance
verifier_agent = Verifier()
full_verifier = FullVerifier()
