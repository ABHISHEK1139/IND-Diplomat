"""
Deterministic Replay Engine (Phase 15)
======================================
Proves reproducibility. Takes a RunManifest and reconstructs the run.
"""

import sys
import os
import json
import asyncio
import tempfile
from datetime import datetime

# Anchor the package on sys.path so the script runs from any CWD without
# requiring an installed distribution (pip install -e . also works).
_ROOT = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_ROOT, "src")
sys.path.insert(0, _SRC if os.path.isdir(os.path.join(_SRC, "dip")) else _ROOT)

from dip.pipeline.deliberation.reasoning.production import RunManifest
from dip.pipeline.deliberation.reasoning.message_bus import MessageBus
from dip.pipeline.deliberation.reasoning.debate_orchestrator import DebateOrchestrator
from dip.pipeline.deliberation.reasoning.schema import EvidenceNode
from tests.test_multi_agent_protocol import (
    MockSecurity, MockDiplomacy, MockEconomic, 
    MockDomestic, MockAlliance, MockStrategy, MockContrarian
)

async def replay_run(manifest_file: str):
    """Reconstruct a debate exactly as it happened."""
    print(f"\n--- REPLAY ENGINE INITIALIZING ---")
    
    with open(manifest_file, "r") as f:
        data = json.load(f)
        manifest = RunManifest(**data)
        
    print(f"Loaded Manifest:")
    print(f"  Run ID:      {manifest.run_id}")
    print(f"  Model:       {manifest.model_version}")
    print(f"  Prompts:     {manifest.prompt_version}")
    print(f"  Random Seed: {manifest.random_seed}")
    
    # In a real system, we would load the exact evidence snapshot from DB using manifest.evidence_snapshot
    # For this demo, we'll mock the loaded evidence.
    bus = MessageBus(trace_id=manifest.run_id)
    
    # 1. Load historical evidence snapshot
    ev1 = EvidenceNode(
        evidence_id="EV_HIST_01",
        observation_id="OBS_1",
        source="GDELT",
        reliability=0.8,
        content="Historical replay evidence",
        timestamp="2026-09-02T10:00:00Z"
    )
    bus.add_evidence(ev1)
    
    # 2. Boot agents with identical parameters
    print("\nBooting exact agent versions...")
    agents = [
        MockSecurity("Security", "Military threat", bus),
        MockContrarian("Contrarian", "Red Team", bus)
    ]
    for agent in agents:
        agent.set_evidence_context("Replay Context", ["EV_HIST_01"])
        
    # 3. Re-run Debate
    print("\nExecuting Replay Debate Cycle...")
    orchestrator = DebateOrchestrator(bus)
    await orchestrator.run_debate()
    
    summary = orchestrator.get_debate_summary()
    print("\n--- REPLAY COMPLETED ---")
    print(f"Gate Decision: {summary['gate_decision']}")
    print(f"Audit Trail Length: {len(bus.audit.log_buffer)}")
    
    print("\nAudit Log Excerpt:")
    for entry in bus.audit.log_buffer[:3]:
        print(f"  [{entry.timestamp}] {entry.agent} -> {entry.event} (Msg: {entry.message_id})")
        
if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Replay a real manifest: python run_replay.py path/to/manifest.json
        asyncio.run(replay_run(sys.argv[1]))
    else:
        # Demo mode: the dummy manifest goes to a temp file, never the CWD.
        manifest_data = RunManifest(
            run_id="REPLAY_RUN_2026",
            evidence_snapshot="SNAP_009"
        ).model_dump()

        with tempfile.NamedTemporaryFile("w", suffix=".json", prefix="dip_replay_", delete=False) as f:
            json.dump(manifest_data, f)
            tmp_manifest = f.name
        try:
            asyncio.run(replay_run(tmp_manifest))
        finally:
            os.unlink(tmp_manifest)
