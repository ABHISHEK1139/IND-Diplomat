
import sys
import os
from unittest.mock import MagicMock

# 1. Mock dependencies BEFORE importing coordinator
sys.modules['Layer4_Analysis.decision.threat_synthesizer'] = MagicMock()
sys.modules['Layer4_Analysis.investigation.anomaly_sentinel'] = MagicMock()

# Mock the classes inside the mocked modules
mock_synth_module = sys.modules['Layer4_Analysis.decision.threat_synthesizer']
mock_sentinel_module = sys.modules['Layer4_Analysis.investigation.anomaly_sentinel']

MockSynthesizerClass = MagicMock()
MockSentinelClass = MagicMock()

mock_synth_module.ThreatSynthesizer = MockSynthesizerClass
mock_sentinel_module.AnomalySentinel = MockSentinelClass

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Now import Coordinator
from engine.Layer4_Analysis.coordinator import CouncilCoordinator
from engine.Layer4_Analysis.council_session import CouncilSession, SessionStatus
from engine.Layer3_StateModel.schemas.state_context import StateContext
from engine.Layer4_Analysis.schema import ThreatLevel, AssessmentReport

def test_anomaly_overrides():
    print("Testing Anomaly Override...")
    
    # Instantiate
    coord = CouncilCoordinator()
    
    # Configure Mocks
    # coord.synthesizer is an instance of MockSynthesizerClass
    # The instantiation happened in __init__
    
    synth_instance = coord.synthesizer
    sentinel_instance = coord.sentinel
    
    # Setup Returns
    normal_report = AssessmentReport(
        threat_level=ThreatLevel.LOW,
        confidence_score=0.9,
        summary="Normal",
        key_indicators=[],
        missing_information=[],
        recommendation="None"
    )
    synth_instance.synthesize.return_value = normal_report
    
    # Create robust state context to avoid attribute errors in signal extraction
    state_data = {
        "actors": { "subject_country": "IND", "target_country": "PAK" },
        "military": { "mobilization_level": 0.1, "exercises": 0, "clash_history": 0 },
        "diplomatic": { "hostility_tone": 0.1, "negotiations": 0.8, "alliances": 0.5 },
        "economic": { "sanctions": 0.0, "trade_dependency": 0.6, "economic_pressure": 0.1 },
        "domestic": { "unrest": 0.1, "regime_stability": 0.9, "protests": 0.0 },
        "capability": { "troop_mobilization": "inactive", "logistics_activity": "low" },
        "evidence": {},
        "meta": {}
    }
    state_context = StateContext.from_dict(state_data)

    # FORCE ANOMALY
    sentinel_instance.check_for_anomaly.return_value = True
    
    # Run
    session = CouncilSession(session_id="test", question="q", state_context=state_context)
    coord.convene_council(session)
    
    # Check
    if session.assessment_report.threat_level == ThreatLevel.ANOMALY:
        print("[PASS] Threat Level is ANOMALY")
    else:
        print(f"[FAIL] Threat Level is {session.assessment_report.threat_level}")
        exit(1)
        
    if session.assessment_report.confidence_score == 0.1:
        print("[PASS] Confidence dropped to 0.1")
    else:
        print(f"[FAIL] Confidence is {session.assessment_report.confidence_score}")
        exit(1)

def test_investigation_trigger():
    print("\nTesting Investigation Trigger...")
    
    coord = CouncilCoordinator()
    synth_instance = coord.synthesizer
    sentinel_instance = coord.sentinel
    
    # Setup: NO Anomaly, but Low Coverage
    sentinel_instance.check_for_anomaly.return_value = False
    
    high_report = AssessmentReport(
        threat_level=ThreatLevel.HIGH,
        confidence_score=0.8,
        summary="War",
        key_indicators=[],
        missing_information=[],
        recommendation="Act"
    )
    synth_instance.synthesize.return_value = high_report
    
    # Setup Reports for Low Coverage
    # We need a minister report
    # Import MinisterReport? It's in council_session
    from engine.Layer4_Analysis.council_session import MinisterReport
    
    mr = MinisterReport(
        minister_name="Test",
        hypothesis="H",
        predicted_signals=["a", "b", "c"],
        matched_signals=[], # 0% coverage
        missing_signals=["a", "b", "c"],
        confidence=0.5,
        reasoning="r"
    )
    
    state_data = {
        "actors": { "subject_country": "IND", "target_country": "PAK" },
        "military": { "mobilization_level": 0.1, "exercises": 0, "clash_history": 0 },
        "diplomatic": { "hostility_tone": 0.1, "negotiations": 0.8, "alliances": 0.5 },
        "economic": { "sanctions": 0.0, "trade_dependency": 0.6, "economic_pressure": 0.1 },
        "domestic": { "unrest": 0.1, "regime_stability": 0.9, "protests": 0.0 },
        "capability": { "troop_mobilization": "inactive", "logistics_activity": "low" },
        "evidence": {},
        "meta": {}
    }
    state_context = StateContext.from_dict(state_data)
    
    session = CouncilSession(session_id="test2", question="q", state_context=state_context)
    session.ministers_reports = [mr]
    
    # Run (direct adjudicate call to avoid full convene overhead if wanted, but convene is fine)
    # We need observed signals for convene
    # Logic: mismatch is calculated in evaluate_evidence inside convene.
    # But here we inject the report with ALREADY calculated mismatch.
    # So we can call _adjudicate directly OR convene.
    # If we call convene, it will overwrite our mismatched signals via _evaluate_evidence.
    # So we call _adjudicate directly.
    
    coord._adjudicate(session, set())
    
    if session.status == SessionStatus.INVESTIGATING:
        print("[PASS] Status is INVESTIGATING")
    else:
        print(f"[FAIL] Status is {session.status}")
        exit(1)
        
    if "Critical Evidence Gap: Verify missing signals." in session.investigation_needs:
        print("[PASS] Found Evidence Gap message")
    else:
        print(f"[FAIL] Missing critical gap message: {session.investigation_needs}")
        exit(1)

if __name__ == "__main__":
    try:
        test_anomaly_overrides()
        test_investigation_trigger()
        print("\nAll Tests Passed.")
    except Exception as e:
        print(f"\n[CRASH] {e}")
        import traceback
        traceback.print_exc()
        exit(1)
