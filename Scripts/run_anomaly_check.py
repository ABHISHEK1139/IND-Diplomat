"""
Fast Anomaly Check.
Runs only evaluation_scenarios/anomaly.json
"""
import json
import uuid
from pathlib import Path
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.Layer3_StateModel.schemas.state_context import StateContext
from engine.Layer4_Analysis.coordinator import CouncilCoordinator
from engine.Layer4_Analysis.council_session import CouncilSession

def run_anomaly_check():
    print("=== Fast Anomaly Check ===\n")
    path = Path("evaluation_scenarios/anomaly.json")
    
    with path.open("r", encoding="utf-8") as f:
        state_data = json.load(f)
        
    state_context = StateContext.from_dict(state_data)
    coordinator = CouncilCoordinator()
    
    session = CouncilSession(
        session_id="anomaly-check",
        question="Analyze threat.",
        state_context=state_context
    )
    
    print("Convening Council...")
    try:
        coordinator.convene_council(session)
        print("Council Adjourned.")
    except Exception as e:
        print(f"Council Failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print(f"Decision: {session.king_decision}")
    print(f"Confidence: {session.final_confidence}")
    print(f"Status: {session.status.name}")
    print(f"Triggers: {session.investigation_needs}")

if __name__ == "__main__":
    run_anomaly_check()
