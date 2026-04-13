"""
Trace Generator.
Runs a scenario and writes a detailed execution log to detailed_system_trace.log.
"""
import json
import sys
import os
from datetime import datetime
from dataclasses import asdict

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.Layer3_StateModel.schemas.state_context import StateContext
from engine.Layer4_Analysis.coordinator import CouncilCoordinator
from engine.Layer4_Analysis.council_session import CouncilSession

LOG_FILE = "detailed_system_trace.log"

def log(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg)

def generate_trace():
    # Clear old log
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(f"=== IND-DIPLOMAT DETAILED TRACE ===\n")
        f.write(f"Timestamp: {datetime.utcnow()}\n")
        f.write("===================================\n\n")

    # Load Scenario (Escalation is interesting)
    scenario_path = "evaluation_scenarios/escalation.json"
    log(f"--- STEP 1: LOAD SCENARIO ({scenario_path}) ---")
    with open(scenario_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    log(f"Scenario Data: {json.dumps(data, indent=2)}\n")

    # Initialize
    ctx = StateContext.from_dict(data)
    coordinator = CouncilCoordinator()
    
    session = CouncilSession(
        session_id="TRACE-001",
        question="Assess the current threat level based on available evidence.",
        state_context=ctx
    )

    log("--- STEP 2: CONVENE COUNCIL ---")
    log(f"User Question: {session.question}")
    
    # Run Pipeline
    # We will manually step through or just run it and inspect the session object
    # Running convenes the council
    coordinator.convene_council(session)

    log("\n--- STEP 3: MINISTER DELIBERATION ---")
    log(f"Ministers convened: {len(session.ministers_reports)}")
    for r in session.ministers_reports:
        log(f"\n[Minister: {r.minister_name}]")
        log(f"  Hypothesis: {r.hypothesis}")
        log(f"  Predicted Signals: {r.predicted_signals}")
        log(f"  Matched Signals: {r.matched_signals}")
        log(f"  Confidence (Base): {r.confidence:.2f}")
        log(f"  Reasoning: {r.reasoning}")

    log("\n--- STEP 4: THREAT SYNTHESIS (FIX 1 & 2) ---")
    if session.assessment_report:
        ar = session.assessment_report
        log(f"Synthesized Threat Level: {ar.threat_level.value}")
        log(f"Grounded Confidence Score: {ar.confidence_score:.4f} (Calculated via Signal * Coverage * Agreement)")
        log(f"Executive Summary: {ar.summary}")
        log(f"Key Indicators: {ar.key_indicators}")
    else:
        log("ERROR: No Assessment Report generated!")

    log("\n--- STEP 5: ANOMALY CHECK (FIX 5) ---")
    # We can infer anomaly status from the final decision or triggers
    log(f"Session Status: {session.status.name}")
    if session.status == "INVESTIGATING":
        log("Investigation Triggered!")
        log(f"Needs: {session.investigation_needs}")
    elif session.assessment_report.threat_level.value == "ANOMALY":
         log("ANOMALY DETECTED by Sentinel.")

    log("\n--- STEP 6: FINAL OUTPUT (FIX 7) ---")
    result = coordinator.generate_result(session)
    log("Final JSON Response (AnalysisResult):")
    # Use default=str to handle Enums and Datetime
    log(json.dumps(result.to_dict(), indent=2, default=str))

    log("\n=== TRACE COMPLETE ===")

if __name__ == "__main__":
    generate_trace()
