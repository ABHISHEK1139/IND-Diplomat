import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

print("Importing StateContext...")
try:
    from engine.Layer3_StateModel.schemas.state_context import StateContext
    print("StateContext OK")
except Exception as e:
    print(f"StateContext Failed: {e}")

print("Importing CouncilSession...")
try:
    from engine.Layer4_Analysis.council_session import CouncilSession
    print("CouncilSession OK")
except Exception as e:
    print(f"CouncilSession Failed: {e}")

print("Importing Ministers...")
try:
    from engine.Layer4_Analysis.ministers import BaseMinister
    print("Ministers OK")
except Exception as e:
    print(f"Ministers Failed: {e}")

print("Importing Coordinator...")
try:
    from engine.Layer4_Analysis.coordinator import CouncilCoordinator
    print("Coordinator OK")
except Exception as e:
    print(f"Coordinator Failed: {e}")

print("Importing Verifier...")
try:
    from engine.Layer4_Analysis.decision.verifier import Verifier
    print("Verifier OK")
except Exception as e:
    print(f"Verifier Failed: {e}")
