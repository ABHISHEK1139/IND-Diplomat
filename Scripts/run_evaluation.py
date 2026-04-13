"""
Surgical Evaluation Runner.
Executes the fix-verification scenarios to prove behavioral correctness.
"""
import json
import uuid
from pathlib import Path
from datetime import datetime
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.Layer3_StateModel.schemas.state_context import StateContext
from engine.Layer4_Analysis.coordinator import CouncilCoordinator
from engine.Layer4_Analysis.council_session import CouncilSession
from engine.Layer4_Analysis.schema import ThreatLevel

SCENARIOS_DIR = Path("evaluation_scenarios")
TARGET_SCENARIOS = [
    "stable.json",
    "escalation.json",
    "trade_pressure.json",
    "deception.json",
    "anomaly.json"
]

def run_evaluation():
    print("=== Surgical Evaluation: Threat Synthesis & Consistency ===\n")
    
    coordinator = CouncilCoordinator()
    results = []
    
    for filename in TARGET_SCENARIOS:
        path = SCENARIOS_DIR / filename
        if not path.exists():
            print(f"[SKIP] {filename} not found.")
            continue
            
        print(f"Running {filename}...")
        
        # Load State
        with path.open("r", encoding="utf-8") as f:
            state_data = json.load(f)
            
        # Ensure schema compliance
        if "meta" not in state_data: state_data["meta"] = {}
        if "evidence" not in state_data: state_data["evidence"] = {}
        
        state_context = StateContext.from_dict(state_data)
        
        # Create Session
        session = CouncilSession(
            session_id=str(uuid.uuid4())[:8],
            question="Analyze the current threat level.",
            state_context=state_context
        )
        
        # Execute
        try:
            coordinator.convene_council(session)
            
            # Extract structured decision
            # We parse the decision string or use internal session state if we exposed the object
            # For now, parsing the string we formatted in coordinator.py
            decision_lines = session.king_decision.split('\n')
            threat_level_str = "UNKNOWN"
            for line in decision_lines:
                if line.startswith("Threat Level:"):
                    threat_level_str = line.split(":")[1].strip()
                    break
            
            result = {
                "scenario": filename,
                "threat_level": threat_level_str,
                "confidence": session.final_confidence,
                "investigation_needs": len(session.investigation_needs),
                "status": session.status.name
            }
            results.append(result)
            
            print(f"  -> Result: {threat_level_str} (Conf: {session.final_confidence:.2f})")
            if session.investigation_needs:
                print(f"  -> Investigation Triggers: {len(session.investigation_needs)}")
                
        except Exception as e:
            print(f"  -> ERROR: {e}")
            import traceback
            traceback.print_exc()

    # Verification Logic
    print("\n\n=== VERIFICATION REPORT ===")
    
    passed = True
    
    # 1. Stable should be LOW/GUARDED
    stable = next((r for r in results if r["scenario"] == "stable.json"), None)
    if stable and stable["threat_level"] in ["LOW", "GUARDED"]:
        print("[PASS] Stable Scenario -> LOW/GUARDED")
    else:
        print(f"[FAIL] Stable Scenario -> {stable['threat_level'] if stable else 'None'}")
        passed = False
        
    # 2. Anomaly should be ANOMALY (or investigating)
    # If using AnomalySentinel, it sets ThreatLevel.ANOMALY
    anomaly = next((r for r in results if r["scenario"] == "anomaly.json"), None)
    if anomaly and anomaly["threat_level"] == "ANOMALY":
        print("[PASS] Anomaly Scenario -> ANOMALY")
    elif anomaly and anomaly["status"] == "INVESTIGATING":
         print("[PASS] Anomaly Scenario -> INVESTIGATING (Acceptable fallback)")
    else:
        print(f"[FAIL] Anomaly Scenario -> {anomaly['threat_level'] if anomaly else 'None'}")
        passed = False
        
    print("\nEvaluation Complete.")
    
if __name__ == "__main__":
    run_evaluation()
