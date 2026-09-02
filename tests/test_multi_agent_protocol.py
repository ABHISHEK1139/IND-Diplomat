"""
Full Integration Test: Phases 1-14 of the IND-Diplomat Multi-Agent Architecture.

Tests the complete flow:
  Schema -> Message Bus -> 7 Specialists -> Debate -> Contrarian Red Team
  -> Verification -> Deterministic Gate -> Groupthink Detection
  -> Belief Revision -> Trajectory -> Backtesting -> Ablation -> Calibration
  -> Global Spillover
"""

import asyncio
import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from dip.pipeline.deliberation.reasoning.schema import (
    AgentMessage, MessageType, BeliefLedger, Belief, EvidenceNode
)
from dip.pipeline.deliberation.reasoning.message_bus import MessageBus
from dip.pipeline.deliberation.reasoning.debate_orchestrator import (
    DebateOrchestrator, OrchestratorState
)
from dip.pipeline.deliberation.reasoning.ministers.base_specialist import BaseSpecialist
from dip.pipeline.deliberation.reasoning.groupthink_detector import GroupthinkDetector
from dip.pipeline.deliberation.reasoning.belief_revision import BeliefTrajectory
from dip.pipeline.deliberation.reasoning.trajectory_engine import TrajectoryEngine
from dip.pipeline.deliberation.reasoning.backtesting import (
    BacktestEngine, ForecastResult, HISTORICAL_CASES
)
from dip.pipeline.deliberation.reasoning.ablation import AblationStudy, AblationConfig
from dip.pipeline.deliberation.reasoning.calibration import CalibrationLoop
from dip.pipeline.deliberation.reasoning.global_spillover import GlobalSpilloverModel
from dip.pipeline.deliberation.reasoning.deterministic_gate import DeterministicGate
from dip.pipeline.deliberation.reasoning.verification_pipeline import VerificationPipeline


# ── Mock Specialists (no LLM needed) ──────────────────────────────────

class MockSecurity(BaseSpecialist):
    async def process_message(self, msg: AgentMessage):
        if msg.message_type == MessageType.EVIDENCE_REQUEST and msg.sender == "Orchestrator":
            await self.update_belief("ACTIVE_CONFLICT", 0.72)
            await self.send_message(
                receiver="BROADCAST", message_type=MessageType.HYPOTHESIS,
                claim="Troop mobilization detected in Kargil sector.",
                round_num=msg.round, state="ACTIVE_CONFLICT",
                probability=0.72, confidence=0.80,
                evidence_ids=["EV_001", "EV_002"],
                reasoning_summary="Forward deployments and logistics surge observed."
            )

class MockDiplomacy(BaseSpecialist):
    async def process_message(self, msg: AgentMessage):
        if msg.message_type == MessageType.EVIDENCE_REQUEST and msg.sender == "Orchestrator":
            await self.update_belief("CRISIS", 0.45)
            await self.send_message(
                receiver="BROADCAST", message_type=MessageType.HYPOTHESIS,
                claim="Diplomatic channels remain open but strained.",
                round_num=msg.round, state="CRISIS",
                probability=0.45, confidence=0.70,
                evidence_ids=["EV_003"],
                reasoning_summary="Backchannel talks ongoing but rhetoric escalating."
            )

class MockEconomic(BaseSpecialist):
    async def process_message(self, msg: AgentMessage):
        if msg.message_type == MessageType.EVIDENCE_REQUEST and msg.sender == "Orchestrator":
            await self.update_belief("ACTIVE_CONFLICT", 0.55)
            await self.send_message(
                receiver="BROADCAST", message_type=MessageType.HYPOTHESIS,
                claim="Trade sanctions suggest economic preparation for conflict.",
                round_num=msg.round, state="ACTIVE_CONFLICT",
                probability=0.55, confidence=0.65,
                evidence_ids=["EV_004"],
                reasoning_summary="Sanctions activity and supply chain repositioning."
            )

class MockDomestic(BaseSpecialist):
    async def process_message(self, msg: AgentMessage):
        if msg.message_type == MessageType.EVIDENCE_REQUEST and msg.sender == "Orchestrator":
            await self.update_belief("CRISIS", 0.50)
            await self.send_message(
                receiver="BROADCAST", message_type=MessageType.HYPOTHESIS,
                claim="Domestic politics may be driving external posturing.",
                round_num=msg.round, state="CRISIS",
                probability=0.50, confidence=0.60,
                evidence_ids=["EV_005"],
                reasoning_summary="Election cycle pressure and nationalist rhetoric."
            )

class MockAlliance(BaseSpecialist):
    async def process_message(self, msg: AgentMessage):
        if msg.message_type == MessageType.EVIDENCE_REQUEST and msg.sender == "Orchestrator":
            await self.update_belief("ACTIVE_CONFLICT", 0.62)
            await self.send_message(
                receiver="BROADCAST", message_type=MessageType.HYPOTHESIS,
                claim="Alliance commitments may draw in additional actors.",
                round_num=msg.round, state="ACTIVE_CONFLICT",
                probability=0.62, confidence=0.72,
                evidence_ids=["EV_006", "EV_007"],
                reasoning_summary="Joint exercise activation and basing agreements."
            )

class MockStrategy(BaseSpecialist):
    async def process_message(self, msg: AgentMessage):
        if msg.message_type == MessageType.EVIDENCE_REQUEST and msg.sender == "Orchestrator":
            await self.update_belief("ACTIVE_CONFLICT", 0.68)
            await self.send_message(
                receiver="BROADCAST", message_type=MessageType.HYPOTHESIS,
                claim="Escalation ladder suggests movement toward limited conflict.",
                round_num=msg.round, state="ACTIVE_CONFLICT",
                probability=0.68, confidence=0.75,
                evidence_ids=["EV_001", "EV_006"],
                reasoning_summary="Red lines approached, off-ramps narrowing."
            )

class MockContrarian(BaseSpecialist):
    async def process_message(self, msg: AgentMessage):
        if msg.message_type == MessageType.EVIDENCE_REQUEST and msg.sender == "Orchestrator":
            if "Contrarian challenge" in msg.claim:
                await self.send_message(
                    receiver="Security", message_type=MessageType.CHALLENGE,
                    claim="[Base-rate attack] Similar troop movements occur regularly during exercises.",
                    round_num=msg.round,
                    reasoning_summary="3 of the last 5 mobilizations were routine exercises, not conflict precursors."
                )


async def run_full_integration_test():
    print("\n" + "="*70)
    print("  IND-DIPLOMAT FULL INTEGRATION TEST — PHASES 1-14")
    print("="*70)

    # ── PHASE 1: Message Bus & Schema ──────────────────────────────────
    print("\n[Phase 1] Message Bus & Schema")
    bus = MessageBus()

    # Add evidence to global memory
    bus.add_evidence(EvidenceNode(
        evidence_id="EV_001", observation_id="OBS_001",
        source="Satellite Imagery", reliability=0.9,
        content="Forward troop deployment detected in Kargil sector",
        timestamp="2026-09-01T12:00:00Z"
    ))
    bus.add_evidence(EvidenceNode(
        evidence_id="EV_002", observation_id="OBS_002",
        source="SIGINT", reliability=0.85,
        content="Encrypted traffic spike on military frequencies",
        timestamp="2026-09-01T14:00:00Z"
    ))
    bus.add_evidence(EvidenceNode(
        evidence_id="EV_003", observation_id="OBS_003",
        source="Diplomatic Cable", reliability=0.75,
        content="Back-channel envoy dispatched to Islamabad",
        timestamp="2026-09-01T16:00:00Z"
    ))
    print(f"  ✓ Evidence memory: {len(bus.evidence_memory)} items")

    # ── PHASE 2: 7 Specialist Agents ───────────────────────────────────
    print("\n[Phase 2] 7 Specialist Agents")
    agents = [
        MockSecurity("Security", "Military threat assessment", bus),
        MockDiplomacy("Diplomacy", "Diplomatic posturing vs negotiation", bus),
        MockEconomic("Economic", "Economic drivers", bus),
        MockDomestic("Domestic", "Domestic politics", bus),
        MockAlliance("Alliance", "Alliance dynamics", bus),
        MockStrategy("Strategy", "Escalation analysis", bus),
        MockContrarian("Contrarian", "Red Team 6-dimension attack", bus),
    ]
    print(f"  ✓ {len(agents)} specialists registered on the bus")

    # ── PHASE 3-4: Debate via Orchestrator ─────────────────────────────
    print("\n[Phase 3-4] Running Debate Orchestrator...")
    orchestrator = DebateOrchestrator(bus)
    await orchestrator.run_debate()
    print(f"  ✓ Debate completed: {len(bus.debate_memory)} messages exchanged")

    # ── PHASE 5: Contrarian Red Team ───────────────────────────────────
    print("\n[Phase 5] Contrarian Red Team Analysis")
    challenges = [m for m in bus.debate_memory if m.message_type == MessageType.CHALLENGE]
    print(f"  ✓ Challenges issued: {len(challenges)}")
    for c in challenges:
        print(f"    → {c.sender} challenges {c.receiver}: {c.claim[:80]}...")

    # ── PHASE 6: Verification ──────────────────────────────────────────
    print("\n[Phase 6] Verification Pipeline")
    verifications = [m for m in bus.debate_memory if m.message_type == MessageType.VERIFICATION_RESULT]
    print(f"  ✓ Verification results: {len(verifications)}")

    # ── PHASE 7: Deterministic Gate ────────────────────────────────────
    print("\n[Phase 7] Deterministic Assessment Gate")
    gate = DeterministicGate(bus)
    decision = gate.evaluate()
    print(f"  ✓ Gate decision: {decision}")

    # ── PHASE 8: Groupthink Detection ──────────────────────────────────
    print("\n[Phase 8] Groupthink Detection")
    detector = GroupthinkDetector(bus)
    gt_result = detector.evaluate()
    print(f"  ✓ Agreement Score:     {gt_result['agreement_score']}")
    print(f"  ✓ Evidence Diversity:  {gt_result['evidence_diversity']}")
    print(f"  ✓ Contrarian Strength: {gt_result['contrarian_strength']}")
    print(f"  ✓ Probability Spread:  {gt_result['probability_spread']}")
    print(f"  ✓ Groupthink Risk:     {gt_result['groupthink_risk']}")
    print(f"  ✓ Warning:             {gt_result['warning']}")

    # ── PHASE 9: Belief Revision & Temporal Memory ─────────────────────
    print("\n[Phase 9] Belief Revision & Temporal Memory")
    bt = BeliefTrajectory()

    # Simulate belief evolution over time
    bt.record("Security", "ACTIVE_CONFLICT", 0.72, "Troop deployment detected", ["EV_001"], 1)
    bt.record("Security", "ACTIVE_CONFLICT", 0.61, "Satellite shows partial withdrawal", ["EV_008"], 2)
    bt.record("Security", "ACTIVE_CONFLICT", 0.77, "New SIGINT contradicts withdrawal", ["EV_002"], 3)
    bt.record("Diplomacy", "CRISIS", 0.45, "Backchannel talks ongoing", ["EV_003"], 1)
    bt.record("Diplomacy", "CRISIS", 0.38, "Joint statement released", ["EV_009"], 2)

    summary = bt.summary()
    for agent, data in summary.items():
        print(f"  ✓ {agent}: P={data['current_probability']} momentum={data['momentum']} "
              f"spike={data['spike_detected']} persistence={data['persistence']}")

    # ── PHASE 10: Trajectory / Early Warning ───────────────────────────
    print("\n[Phase 10] Trajectory / Early Warning Engine")
    engine = TrajectoryEngine(bt, bus)
    forecast = engine.generate_forecast()
    for horizon, dist in forecast["trajectories"].items():
        print(f"  ✓ {horizon}: dominant={dist['dominant_state']} "
              f"confidence={dist['confidence']} black_swan={dist['black_swan_risk']}")
        probs = dist["probabilities"]
        for state, p in probs.items():
            bar = "█" * int(p * 30)
            print(f"      {state:<20} {p:.3f} {bar}")
    if forecast["early_warnings"]:
        print(f"  ⚠ Early Warnings: {len(forecast['early_warnings'])}")
        for w in forecast["early_warnings"]:
            print(f"    → [{w['trigger_type']}] {w['message']}")

    # ── PHASE 11: Historical Backtesting ───────────────────────────────
    print("\n[Phase 11] Historical Backtesting")
    bt_engine = BacktestEngine()
    mock_results = [
        ForecastResult(case_id="KARGIL_1999", predicted_state="ACTIVE_CONFLICT",
                       predicted_probability=0.78, lead_time_days=12),
        ForecastResult(case_id="GALWAN_2020", predicted_state="LIMITED_CONFLICT",
                       predicted_probability=0.55, lead_time_days=3),
        ForecastResult(case_id="DOKLAM_2017", predicted_state="CRISIS",
                       predicted_probability=0.38, lead_time_days=7),
        ForecastResult(case_id="BALAKOT_2019", predicted_state="LIMITED_CONFLICT",
                       predicted_probability=0.70, lead_time_days=5),
        ForecastResult(case_id="TAIWAN_STRAIT_2022", predicted_state="CRISIS",
                       predicted_probability=0.42, lead_time_days=2),
    ]
    for r in mock_results:
        bt_engine.add_result(r)
    metrics = bt_engine.compute_metrics()
    print(f"  ✓ Brier Score:      {metrics.brier_score}")
    print(f"  ✓ Calibration Err:  {metrics.calibration_error}")
    print(f"  ✓ Precision:        {metrics.precision}")
    print(f"  ✓ Recall:           {metrics.recall}")
    print(f"  ✓ Mean Lead Time:   {metrics.mean_lead_time} days")
    print(f"  ✓ False Alarm Rate: {metrics.false_alarm_rate}")

    # ── PHASE 12: Ablation Study ───────────────────────────────────────
    print("\n[Phase 12] Ablation Study")
    ablation = AblationStudy()
    ablation.run_config(AblationConfig.FULL, mock_results)
    # Simulate degraded results without Contrarian
    degraded = [
        ForecastResult(case_id="KARGIL_1999", predicted_state="ACTIVE_CONFLICT",
                       predicted_probability=0.85, lead_time_days=8),
        ForecastResult(case_id="GALWAN_2020", predicted_state="ACTIVE_CONFLICT",
                       predicted_probability=0.72, lead_time_days=2),
        ForecastResult(case_id="DOKLAM_2017", predicted_state="ACTIVE_CONFLICT",
                       predicted_probability=0.55, lead_time_days=5),
        ForecastResult(case_id="BALAKOT_2019", predicted_state="LIMITED_CONFLICT",
                       predicted_probability=0.75, lead_time_days=4),
        ForecastResult(case_id="TAIWAN_STRAIT_2022", predicted_state="LIMITED_CONFLICT",
                       predicted_probability=0.60, lead_time_days=1),
    ]
    ablation.run_config(AblationConfig.NO_CONTRARIAN, degraded)
    abl_summary = ablation.summary()
    for row in abl_summary["ablation_results"]:
        print(f"  ✓ {row['config']}: Brier={row['brier_score']} "
              f"ΔBrier={row['delta_brier']:+.4f} Verdict={row['verdict']}")
    print(f"  Conclusion: {abl_summary['conclusion']}")

    # ── PHASE 13: Calibration / Learning Loop ──────────────────────────
    print("\n[Phase 13] Calibration / Learning Loop")
    cal = CalibrationLoop()
    cal.archive_forecast("F001", "Kargil assessment", "ACTIVE_CONFLICT", 0.78,
                         {"Security": 0.72, "Diplomacy": 0.45, "Strategy": 0.68})
    cal.record_outcome("F001", "ACTIVE_CONFLICT", 0.85)
    cal.archive_forecast("F002", "Doklam assessment", "CRISIS", 0.38,
                         {"Security": 0.30, "Diplomacy": 0.55, "Strategy": 0.35})
    cal.record_outcome("F002", "CRISIS", 0.40)
    weights = cal.get_agent_weights()
    for agent, w in weights.items():
        print(f"  ✓ {agent}: weight={w:.4f}")
    cal_summary = cal.summary()
    print(f"  ✓ Total archived: {cal_summary['total_archived']}, "
          f"Resolved: {cal_summary['resolved']}")

    # ── PHASE 14: Global Spillover Model ───────────────────────────────
    print("\n[Phase 14] Global / Cross-Theater Spillover Model")
    gsm = GlobalSpilloverModel()
    result = gsm.simulate_spillover("Taiwan_Strait", tension_increase=0.70)
    print(f"  Source: {result.source_theater} (tension={result.source_tension:.2f})")
    print(f"  Affected theaters:")
    for theater, tension in sorted(result.affected_theaters.items(), key=lambda x: -x[1]):
        bar = "█" * int(tension * 30)
        print(f"    {theater:<25} {tension:.3f} {bar}")
    print(f"  Propagation chain:")
    for step in result.propagation_chain:
        print(f"    → {step}")

    # ── FINAL SUMMARY ──────────────────────────────────────────────────
    print("\n" + "="*70)
    print("  ALL 14 PHASES EXECUTED SUCCESSFULLY")
    print("="*70)
    print(f"""
  ✅ Phase 1:  Message Schema + Bus
  ✅ Phase 2:  7 Specialized Mandates
  ✅ Phase 3:  Evidence-Aware Agents
  ✅ Phase 4:  Real Cross-Agent Debate
  ✅ Phase 5:  Contrarian Red Team
  ✅ Phase 6:  CoVe + CRAG Verification
  ✅ Phase 7:  Deterministic Judgment      → {decision}
  ✅ Phase 8:  Groupthink Detection        → Risk: {gt_result['groupthink_risk']}
  ✅ Phase 9:  Belief Revision + Temporal  → {len(bt.trajectories)} trajectories
  ✅ Phase 10: Trajectory / Early Warning  → {len(forecast['early_warnings'])} warnings
  ✅ Phase 11: Historical Backtesting      → Brier: {metrics.brier_score}
  ✅ Phase 12: Ablation Study              → {len(abl_summary['ablation_results'])} configs tested
  ✅ Phase 13: Calibration / Learning      → {cal_summary['resolved']} forecasts calibrated
  ✅ Phase 14: Global Spillover Model      → {len(result.affected_theaters)} theaters affected
""")


if __name__ == "__main__":
    asyncio.run(run_full_integration_test())
