"""
Test Phase-4 Deliberative Reasoning Logic.
"""
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.Layer3_StateModel.schemas.state_context import StateContext
from engine.Layer4_Analysis.council_session import CouncilSession, SessionStatus
from engine.Layer4_Analysis.coordinator import CouncilCoordinator
from engine.Layer4_Analysis.report_generator import generate_assessment

def test_deliberation_cycle():
    print("\n--- Testing Phase-4 Deliberation Cycle ---")
    
    # 1. Mock State (High Tension)
    ctx = StateContext.from_dict({
        "actors": {"subject_country": "CountryA", "target_country": "CountryB"},
        "military": {"mobilization_level": 0.8, "exercises": 5, "clash_history": 0},
        "diplomatic": {"hostility_tone": 0.7, "negotiations": 0.2, "alliances": 0.0},
        "economic": {"sanctions": 0.1, "trade_dependency": 0.2, "economic_pressure": 0.0},
        "domestic": {"unrest": 0.3, "regime_stability": 0.8, "protests": 0.0},
        "capability": {
            "troop_mobilization": "high", 
            "logistics_activity": "medium",
            "supply_stockpiling": "none",
            "cyber_activity": "low",
            "evacuation_activity": "none"
        },
        "meta": {"data_confidence": 0.9, "time_recency": 1.0}
    })
    
    # 2. visual check
    print(f"State: {ctx.summary()}")
    
    # 3. Create Session
    session = CouncilSession(
        session_id="test_001",
        question="Is CountryA preparing for war?",
        state_context=ctx
    )
    
    # 4. Coordinator Convene
    coordinator = CouncilCoordinator()
    
    # Mock EvidenceTracker for test (since we don't have real evidence linkage)
    # We simulate observed signals matching the military hypothesis
    class MockTracker:
        def extract_observed_signals(self, *args):
            return {"troop_staging", "logistics_movement", "aggressive_rhetoric"}
    
    coordinator.evidence_tracker = MockTracker()
    
    print("Convening Council...")
    session = coordinator.convene_council(session)
    
    # 5. Verify Outcome
    print("\nMinisters Reports:")
    for report in session.ministers_reports:
        print(f"[{report.minister_name}] Conf: {report.confidence:.2f}")
        print(f"  Hypothesis: {report.hypothesis}")
        print(f"  Matched: {report.matched_signals}")
    
    print(f"\nKing Decision: {session.king_decision}")
    print(f"Final Confidence: {session.final_confidence}")
    
    assert session.status == SessionStatus.CONCLUDED
    assert session.king_decision is not None
    assert "military action" in session.king_decision
    assert session.final_confidence > 0.6
    
    # 6. Generate Report
    report_text = generate_assessment(session)
    print("\n--- Final Report ---")
    print(report_text)
    print("--------------------")

if __name__ == "__main__":
    test_deliberation_cycle()
