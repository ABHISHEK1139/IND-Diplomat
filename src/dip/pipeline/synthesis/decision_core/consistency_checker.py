"""
Consistency Checker.
Validates the deterministically generated IntelligenceAssessment against logical contradictions.
"""
from dip.core.schema import IntelligenceAssessment

def validate_assessment(assessment: IntelligenceAssessment) -> None:
    """
    Validates the assessment for internal logical contradictions.
    Throws a ValueError if a critical contradiction is found.
    """
    # 1. Threat Level vs Dimensional Threats
    max_dimension = max(
        assessment.threat_dimensions.military,
        assessment.threat_dimensions.diplomatic,
        assessment.threat_dimensions.economic,
        assessment.threat_dimensions.cyber,
        assessment.threat_dimensions.information
    )
    
    if assessment.overall_threat_level == "LOW" and max_dimension > 0.7:
        raise ValueError(f"Consistency Error: Overall threat is LOW, but dimensional threat is HIGH ({max_dimension}).")
        
    # 2. Confidence vs Evidence Quality
    if assessment.overall_confidence > 0.8 and not assessment.positive_evidence:
        raise ValueError("Consistency Error: HIGH confidence with zero positive evidence.")
        
    # 3. High Threat without verified evidence
    verified_evidence_exists = any(
        getattr(s, "verification_status", "") == "Verified" or getattr(s, "confidence", 0.0) >= 0.7 
        for s in assessment.positive_evidence
    )
    if assessment.overall_threat_level in ["HIGH", "CRITICAL"] and not verified_evidence_exists:
        raise ValueError("Consistency Error: Cannot assign HIGH threat without verified evidence.")

    # Mark as stable if it passed
    assessment.assessment_stability = "Verified & Stable"

