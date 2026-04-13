
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.Layer4_Analysis.council_session import CouncilSession, MinisterReport, SessionStatus
from engine.Layer3_StateModel.schemas.state_context import StateContext
from engine.Layer4_Analysis.schema import ThreatLevel, AssessmentReport

# We must import Coordinator AFTER patching, or patch where it is used.
# Since we import it, we should patch the class in the module where it is defined or used.
# But Coordinator imports them at top level.

class TestCoordinatorAnomaly(unittest.TestCase):
    
    @patch('Layer4_Analysis.coordinator.ThreatSynthesizer')
    @patch('Layer4_Analysis.coordinator.AnomalySentinel')
    def test_anomaly_override(self, MockSentinel, MockSynthesizer):
        """Test that AnomalySentinel overrides the assessment."""
        from engine.Layer4_Analysis.coordinator import CouncilCoordinator
        
        # Setup Mocks
        coordinator = CouncilCoordinator()
        
        # Verify mocks are used
        self.assertTrue(isinstance(coordinator.synthesizer, MagicMock))
        self.assertTrue(isinstance(coordinator.sentinel, MagicMock))
        
        # 1. Setup Session
        session = CouncilSession(
            session_id="test_anomaly",
            question="q",
            state_context=StateContext(meta={}, evidence={})
        )
        
        # 2. Setup Mock Assessment (Normal)
        normal_assessment = AssessmentReport(
            threat_level=ThreatLevel.LOW,
            confidence_score=0.9,
            summary="All good",
            key_indicators=[],
            missing_information=[],
            recommendation="Chill"
        )
        coordinator.synthesizer.synthesize.return_value = normal_assessment
        
        # 3. Setup Anomaly Trigger
        coordinator.sentinel.check_for_anomaly.return_value = True
        
        # 4. Run Adjudicate
        observed = {"signal_a", "signal_b", "signal_c"}
        coordinator._adjudicate(session, observed)
        
        # 5. Assertions
        # Should be ANOMALY
        # Note: If _adjudicate modifies the assessment object or creates a new one, we check session state
        self.assertEqual(session.assessment_report.threat_level, ThreatLevel.ANOMALY)
        self.assertIn("[ANOMALY DETECTED]", session.assessment_report.summary)
        self.assertEqual(session.assessment_report.confidence_score, 0.1)
        
    @patch('Layer4_Analysis.coordinator.ThreatSynthesizer')
    @patch('Layer4_Analysis.coordinator.AnomalySentinel')
    def test_investigation_trigger_low_coverage(self, MockSentinel, MockSynthesizer):
        """Test that low evidence coverage triggers investigation."""
        from engine.Layer4_Analysis.coordinator import CouncilCoordinator
        
        coordinator = CouncilCoordinator()
        
        # 1. Setup Session with Reports having low match rate
        session = CouncilSession(
            session_id="test_investigation",
            question="q",
            state_context=StateContext(meta={}, evidence={})
        )
        
        report = MinisterReport(
            minister_name="Sec",
            hypothesis="War",
            predicted_signals=["tank_move", "cyber_attack", "comm_silence"], # 3 predicted
            matched_signals=["tank_move"], # 1 matched (33% coverage)
            missing_signals=["cyber_attack", "comm_silence"],
            confidence=0.5,
            reasoning="Checking"
        )
        session.ministers_reports = [report]
        
        # 2. Setup Mock Assessment
        coordinator.synthesizer.synthesize.return_value = AssessmentReport(
            threat_level=ThreatLevel.HIGH, # Even if synthesized as HIGH
            confidence_score=0.7,
            summary="Bad",
            key_indicators=[],
            missing_information=[],
            recommendation="Panic"
        )
        
        # 3. No Anomaly
        coordinator.sentinel.check_for_anomaly.return_value = False
        
        # 4. Run Adjudicate
        coordinator._adjudicate(session, set())
        
        # 5. Assertions
        # Should be INVESTIGATING because coverage (1/3 = 0.33) < 0.4
        self.assertEqual(session.status, SessionStatus.INVESTIGATING)
        # Check that one of the investigation needs is the specific message
        self.assertTrue(any("Critical Evidence Gap" in need for need in session.investigation_needs))

if __name__ == '__main__':
    unittest.main()
