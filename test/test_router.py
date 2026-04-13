import sys
import os
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.Layer3_StateModel.interface.state_provider import build_initial_state
from test._support import script_log_path

def test_router():
    log_path = script_log_path("router_results.log")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("=== Testing Query Router ===\n")
        
        # 1. Semantic Query
        query = "Why did the 2020 border conflict happen?"
        f.write(f"\nQuery: {query}\n")
        state = build_initial_state(query, "IND")
        f.write(f"Evidence Reasoning: {state.evidence.rag_reasoning}\n")
        f.write(f"RAG Docs Count: {len(state.evidence.rag_documents)}\n")
        
        if "Routed to RAG" in state.evidence.rag_reasoning or "RAG unavailable" in state.evidence.rag_reasoning:
            f.write("PASS: Attempted route to RAG.\n")
        else:
            f.write("FAIL: Did not route to RAG.\n")

        # 2. Stats Query
        query = "What is the GDP of India?"
        f.write(f"\nQuery: {query}\n")
        state_stats = build_initial_state(query, "IND")
        f.write(f"Evidence Reasoning: {state_stats.evidence.rag_reasoning}\n")
        
        if not state_stats.evidence.rag_reasoning:
            f.write("PASS: Correctly skipped RAG.\n")
        else:
            f.write(f"FAIL: Unexpectedly routed to RAG: {state_stats.evidence.rag_reasoning}\n")

if __name__ == "__main__":
    test_router()
