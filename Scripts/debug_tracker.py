
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    print("Importing EvidenceTracker...")
    from engine.Layer4_Analysis.evidence.evidence_tracker import extract_signals_from_state
    print("Success!")
except Exception as e:
    import traceback
    traceback.print_exc()
