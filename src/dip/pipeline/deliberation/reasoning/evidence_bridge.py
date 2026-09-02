"""
Evidence Bridge (Phase 3)
=========================
Connects the real IND-Diplomat evidence chain (StateContext → Signal → Belief)
to the structured Message Bus and Specialist agents.

The bridge:
1. Takes a StateContext from Layer 3
2. Converts Signals into EvidenceNode objects for the Global Evidence Memory
3. Builds per-agent evidence bundles filtered by domain
4. Injects evidence into the Message Bus before the debate begins
"""

import logging
import hashlib
from typing import Dict, List, Optional

from dip.core.schema import StateContext, Signal, Belief, RawObservation
from dip.pipeline.deliberation.reasoning.schema import EvidenceNode, AgentMessage, MessageType
from dip.pipeline.deliberation.reasoning.message_bus import MessageBus

logger = logging.getLogger("Layer4.EvidenceBridge")


# Which signal domains map to which specialist agents
DOMAIN_AGENT_MAP: Dict[str, List[str]] = {
    "military":    ["Security", "Strategy", "Alliance"],
    "diplomatic":  ["Diplomacy", "Alliance", "Strategy"],
    "economic":    ["Economic", "Strategy"],
    "internal":    ["Domestic", "Economic"],
    "political":   ["Domestic", "Diplomacy"],
    "cyber":       ["Security", "Strategy"],
    "legal":       ["Diplomacy", "Alliance"],
    "intelligence": ["Security", "Strategy", "Contrarian"],
    "unknown":     ["Security", "Diplomacy", "Economic", "Domestic", "Alliance", "Strategy", "Contrarian"],
}


def signal_to_evidence(signal: Signal, index: int) -> EvidenceNode:
    """Convert a Layer 2 Signal into an EvidenceNode for the Message Bus."""
    evidence_id = f"EV_{hashlib.md5(f'{signal.entity}_{signal.action}_{index}'.encode()).hexdigest()[:8]}"
    return EvidenceNode(
        evidence_id=evidence_id,
        observation_id=signal.source_ref,
        source=signal.source_ref,
        reliability=signal.reliability_score,
        content=f"{signal.entity} {signal.action}" + (f" targeting {signal.target}" if signal.target else ""),
        timestamp=signal.timestamp or "",
    )


def build_agent_evidence_bundle(signals: List[Signal], agent_name: str) -> List[EvidenceNode]:
    """
    Filter signals by domain relevance for a specific agent,
    then convert to EvidenceNode objects.
    """
    relevant: List[EvidenceNode] = []
    for i, sig in enumerate(signals):
        domain = sig.domain.lower() if sig.domain else "unknown"
        allowed_agents = DOMAIN_AGENT_MAP.get(domain, DOMAIN_AGENT_MAP["unknown"])
        if agent_name in allowed_agents:
            relevant.append(signal_to_evidence(sig, i))
    return relevant


def inject_evidence_into_bus(state_context: StateContext, bus: MessageBus) -> Dict[str, List[str]]:
    """
    Load all signals from StateContext into the Global Evidence Memory
    and return a mapping of agent_name → [evidence_ids] for targeted delivery.
    """
    agent_evidence_map: Dict[str, List[str]] = {}
    all_agents = ["Security", "Diplomacy", "Economic", "Domestic", "Alliance", "Strategy", "Contrarian"]

    # 1. Convert ALL signals to evidence and add to global memory
    for i, sig in enumerate(state_context.current_signals):
        ev = signal_to_evidence(sig, i)
        bus.add_evidence(ev)

    # 2. Build per-agent bundles
    for agent in all_agents:
        bundle = build_agent_evidence_bundle(state_context.current_signals, agent)
        agent_evidence_map[agent] = [ev.evidence_id for ev in bundle]

    logger.info(
        f"[EvidenceBridge] Injected {len(bus.evidence_memory)} evidence nodes. "
        f"Agent bundles: {', '.join(f'{a}={len(ids)}' for a, ids in agent_evidence_map.items())}"
    )

    return agent_evidence_map


def build_evidence_context_prompt(
    state_context: StateContext,
    agent_name: str,
    evidence_map: Dict[str, List[str]],
    bus: MessageBus,
) -> str:
    """
    Build a structured evidence context string for an agent's LLM prompt.
    Instead of dumping raw documents, gives the agent:
      - Evidence IDs it should cite
      - Source reliability scores
      - Signal descriptions with domains
      - Belief summaries from Layer 3
      - Temporal indicators
    """
    lines = [f"=== EVIDENCE BUNDLE FOR {agent_name} ==="]
    lines.append(f"Country: {state_context.country}")
    lines.append(f"Total observations: {state_context.observation_count}")
    lines.append("")

    # Evidence nodes assigned to this agent
    my_evidence_ids = evidence_map.get(agent_name, [])
    lines.append(f"--- Assigned Evidence ({len(my_evidence_ids)} items) ---")
    for eid in my_evidence_ids:
        ev = bus.evidence_memory.get(eid)
        if ev:
            lines.append(
                f"  [{ev.evidence_id}] {ev.content} "
                f"(source={ev.source}, reliability={ev.reliability:.2f}, time={ev.timestamp})"
            )

    # Beliefs from Layer 3
    lines.append("")
    lines.append(f"--- Layer 3 Beliefs ({len(state_context.beliefs)} items) ---")
    for belief in state_context.beliefs:
        lines.append(
            f"  {belief.signal_code}: support={belief.support_score:.2f}, "
            f"level={belief.belief_level}, sources={belief.source_count}, "
            f"recency={belief.recency_weight:.2f}"
        )

    # Temporal indicators
    if state_context.temporal_indicators:
        lines.append("")
        lines.append(f"--- Temporal Indicators ({len(state_context.temporal_indicators)} items) ---")
        for ti in state_context.temporal_indicators:
            lines.append(f"  {ti}")

    # Escalation state
    if state_context.escalation:
        lines.append("")
        lines.append(f"--- Escalation State ---")
        lines.append(f"  {state_context.escalation}")

    # Contradictions
    if state_context.contradictions:
        lines.append("")
        lines.append(f"--- Contradictions ({len(state_context.contradictions)}) ---")
        for c in state_context.contradictions:
            lines.append(f"  {c}")

    # Intelligence gaps
    if state_context.intelligence_gaps:
        lines.append("")
        lines.append(f"--- Intelligence Gaps ({len(state_context.intelligence_gaps)}) ---")
        for g in state_context.intelligence_gaps:
            lines.append(f"  {g}")

    return "\n".join(lines)
