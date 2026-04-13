"""
Validation Suite Runner
Executes the Council of Ministers against synthetic scenarios to validate reasoning behaviors.
"""
import json
import uuid
import glob
import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.Layer3_StateModel.schemas.state_context import StateContext
from engine.Layer4_Analysis.coordinator import CouncilCoordinator
from engine.Layer4_Analysis.council_session import CouncilSession
from engine.Layer4_Analysis.intake.analyst_input_builder import build_analyst_input
from test._support import PROJECT_ROOT, script_log_path

# Scenario -> Question Map
QUESTION_MAP = {
    "scenario_1_high_tension.json": "Analyze the current threat level of India.",
    "scenario_2_low_tension.json": "Analyze the current threat level of India.",
    "scenario_3_insufficient.json": "Why is war likely?",
    "scenario_4_contradiction.json": "Assess the stability of the relationship.",
    "scenario_5_anomaly.json": "Analyze recent events for anomalies.",
    "scenario_sensitivity_1.json": "Is conflict likely?",
    "scenario_sensitivity_2.json": "Is conflict likely?",
    "scenario_sensitivity_3.json": "Is conflict likely?",
    "scenario_sensitivity_4.json": "Is conflict likely?",
    "scenario_sensitivity_5.json": "Is conflict likely?",
}

DEFAULT_QUESTION = "Assess the current situation."

def run_suite():
    scenarios_dir = PROJECT_ROOT / "evaluation_scenarios"
    log_file = script_log_path("validation_suite.log")
    
    print(f"Starting Validation Suite...")
    print(f"Scenarios Directory: {scenarios_dir.resolve()}")
    
    coordinator = CouncilCoordinator()
    
    results = []
    
    with log_file.open("w", encoding="utf-8") as log:
        log.write(f"=== IND-DIPLOMAT VALIDATION SUITE REPORT ===\n")
        log.write(f"Date: {datetime.now().isoformat()}\n\n")
        
        scenario_files = sorted(list(scenarios_dir.glob("*.json")))
        
        for scenario_path in scenario_files:
            filename = scenario_path.name
            question = QUESTION_MAP.get(filename, DEFAULT_QUESTION)
            
            print(f"Running Scenario: {filename}...")
            log.write(f"--- Scenario: {filename} ---\n")
            log.write(f"Question: {question}\n")
            
            try:
                # 1. Load State
                with scenario_path.open("r", encoding="utf-8") as f:
                    state_data = json.load(f)
                
                # Deserialization Fix: Ensure meta and evidence exist if missing in JSON
                if "meta" not in state_data:
                    state_data["meta"] = {}
                if "evidence" not in state_data:
                    state_data["evidence"] = {}
                    
                state_context = StateContext.from_dict(state_data)
                
                # 2. Convene Council
                session_id = str(uuid.uuid4())[:8]
                session = CouncilSession(
                    session_id=session_id,
                    question=question,
                    state_context=state_context
                )
                
                # Run reasoning
                coordinator.convene_council(session)
                
                # 3. Log Results
                decision = session.king_decision
                confidence = session.final_confidence
                
                log.write(f"Decision: {decision}\n")
                log.write(f"Confidence: {confidence:.2f}\n")
                log.write(f"Analysis Status: {session.status.value}\n")
                
                if session.identified_conflicts:
                    log.write(f"Conflicts: {session.identified_conflicts}\n")
                
                log.write("Ministers' Hypotheses:\n")
                for report in session.ministers_reports:
                    log.write(f"  - [{report.minister_name}] {report.hypothesis} (Conf: {report.confidence:.2f})\n")
                
                results.append({
                    "scenario": filename,
                    "decision": decision,
                    "confidence": confidence
                })
                
                log.write("\n")
                
            except Exception as e:
                print(f"ERROR in {filename}: {e}")
                log.write(f"ERROR: {e}\n\n")
                import traceback
                traceback.print_exc()

        log.write("=== SUMMARY ===\n")
        print("\n=== Validation Summary ===")
        for res in results:
            summary_line = f"{res['scenario']}: {res['decision']} (Conf: {res['confidence']:.2f})"
            log.write(summary_line + "\n")
            print(summary_line)
            
    print(f"\nValidation Suite Complete. Report saved to {log_file.name}")

if __name__ == "__main__":
    run_suite()
