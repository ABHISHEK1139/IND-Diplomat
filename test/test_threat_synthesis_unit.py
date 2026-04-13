
import unittest
from unittest.mock import MagicMock, patch
import sys
import os
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.Layer4_Analysis.decision.threat_synthesizer import ThreatSynthesizer, ThreatAssessment
from engine.Layer4_Analysis.council_session import MinisterReport

class TestThreatSynthesizer(unittest.TestCase):
    def setUp(self):
        self.synthesizer = ThreatSynthesizer()
        # Mock the LLM to avoid actual generation
        self.synthesizer.llm = MagicMock()

    def test_synthesis_parsing(self):
        # Mock Reports
        reports = [
            MinisterReport(
                minister_name="Security", 
                hypothesis="Low threat", 
                confidence=0.8, 
                reasoning="None", 
                predicted_signals=[],
                matched_signals=[],
                missing_signals=[]
            ),
            MinisterReport(
                minister_name="Diplomatic", 
                hypothesis="Peaceful", 
                confidence=0.7, 
                reasoning="Talks", 
                predicted_signals=[],
                matched_signals=[],
                missing_signals=[]
            )
        ]
        
        # Mock LLM Response
        mock_json = """
        ```json
        {
            "threat_level": "LOW",
            "risk_score": 0.2,
            "executive_summary": "No immediate threat detected.",
            "synthesis_logic": "All ministers indicate calm.",
            "key_drivers": ["Diplomatic Engagement"]
        }
        ```
        """
        self.synthesizer.llm.generate.return_value = mock_json
        
        # Execute
        assessment = self.synthesizer.synthesize(reports, set())
        
        # Verify
        self.assertIsInstance(assessment, ThreatAssessment)
        self.assertEqual(assessment.level, "LOW")
        self.assertEqual(assessment.score, 0.2)
        self.assertEqual(assessment.summary, "No immediate threat detected.")
        self.assertEqual(assessment.primary_drivers, ["Diplomatic Engagement"])
        print("\n[Passed] ThreatSynthesizer correctly parses LLM JSON.")

    def test_synthesis_failure_handling(self):
        # Test malformed JSON handling
        self.synthesizer.llm.generate.return_value = "Not JSON"
        
        reports = [
            MinisterReport(
                minister_name="Security", 
                hypothesis="Low", 
                confidence=0.8, 
                reasoning="", 
                predicted_signals=[],
                matched_signals=[],
                missing_signals=[]
            )
        ]
        assessment = self.synthesizer.synthesize(reports, set())
        
        self.assertEqual(assessment.level, "ERROR")
        print("\n[Passed] ThreatSynthesizer handles LLM failure gracefully.")

if __name__ == "__main__":
    unittest.main()
