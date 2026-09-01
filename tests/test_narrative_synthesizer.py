import pytest
from dip.pipeline.synthesis.presentation.narrative_synthesizer import narrative_synthesizer

def test_strategic_narrative_synthesis():
    briefing = narrative_synthesizer.synthesize(
        query="Assess Baltic air defense integration",
        country="EST",
        threat_level="ELEVATED",
        verification_score=0.88,
        hypotheses=[],
        sre_data={"military_escalation": 0.65, "diplomatic_tension": 0.50, "economic_pressure": 0.40},
        legal_citations=["UN_CHARTER (Article 51)"]
    )
    
    assert briefing.executive_judgment != ""
    assert "HIGH CONFIDENCE" in briefing.estimative_confidence
    assert len(briefing.key_judgments) >= 3
    assert "UN_CHARTER" in briefing.raw_markdown
    assert len(briefing.actionable_options) >= 2
