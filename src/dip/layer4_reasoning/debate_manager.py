"""
Debate Manager (LangGraph)
==========================
Uses LangGraph to orchestrate the peer review simulation:
Opinion -> Challenge -> Evidence -> Consensus.
"""

import logging
from typing import TypedDict, List, Dict, Any, Annotated
import operator

try:
    from langgraph.graph import StateGraph, END
except ImportError:
    StateGraph = None
    END = None

from dip.layer4_reasoning.evidence_judge import EvidenceJudge
from dip.layer4_reasoning.devils_advocate import DevilsAdvocate

logger = logging.getLogger("Layer4.DebateManager")


class DebateState(TypedDict):
    topic: str
    world_model: Any
    expert_hypotheses: List[Dict[str, Any]]
    challenges: List[Dict[str, Any]]
    evidence_verdicts: List[str]
    consensus: Dict[str, Any]
    devils_critique: Dict[str, Any]
    iteration: int


class DebateManager:
    """
    State machine orchestrating the Council Debate via LangGraph.
    """
    def __init__(self):
        self.evidence_judge = EvidenceJudge()
        self.devils_advocate = DevilsAdvocate()
        
        if StateGraph:
            workflow = StateGraph(DebateState)
            workflow.add_node("challenge_round", self.node_challenge)
            workflow.add_node("evidence_round", self.node_evidence)
            workflow.add_node("consensus_round", self.node_consensus)
            workflow.add_node("red_team_round", self.node_red_team)
            
            workflow.set_entry_point("challenge_round")
            workflow.add_edge("challenge_round", "evidence_round")
            workflow.add_edge("evidence_round", "consensus_round")
            workflow.add_edge("consensus_round", "red_team_round")
            workflow.add_edge("red_team_round", END)
            
            self.graph = workflow.compile()
        else:
            self.graph = None

    async def node_challenge(self, state: DebateState) -> DebateState:
        logger.info("Debate: Challenge Round")
        # In a real setup, experts would critique each other here.
        # For this skeleton, we assume experts have generated hypotheses in the orchestrator.
        state["challenges"] = [{"target": "H1", "critique": "Lacks economic backing"}]
        return state

    async def node_evidence(self, state: DebateState) -> DebateState:
        logger.info("Debate: Evidence Verification Round")
        verdicts = []
        # Judge every claim
        for hyp in state.get("expert_hypotheses", []):
            for claim in hyp.get("matched_signals", []):
                verdict = await self.evidence_judge.judge_claim(claim, state["world_model"], state["topic"])
                verdicts.append(verdict)
        state["evidence_verdicts"] = verdicts
        return state

    async def node_consensus(self, state: DebateState) -> DebateState:
        logger.info("Debate: Consensus Round")
        # A Tier 3 model would synthesize the hypotheses here.
        state["consensus"] = {
            "hypothesis": "Unified Hypothesis based on evidence.",
            "confidence": 0.75
        }
        return state

    async def node_red_team(self, state: DebateState) -> DebateState:
        logger.info("Debate: Red Team Round (Devil's Advocate)")
        critique = await self.devils_advocate.critique(
            state["consensus"]["hypothesis"], 
            state["world_model"], 
            state["topic"]
        )
        state["devils_critique"] = critique
        return state

    async def run_debate(self, topic: str, world_model, expert_hypotheses: List[Dict]) -> DebateState:
        """Executes the full LangGraph debate."""
        if not self.graph:
            logger.error("LangGraph not installed. Returning empty debate.")
            return {}
            
        initial_state = {
            "topic": topic,
            "world_model": world_model,
            "expert_hypotheses": expert_hypotheses,
            "challenges": [],
            "evidence_verdicts": [],
            "consensus": {},
            "devils_critique": {},
            "iteration": 0
        }
        
        result = await self.graph.ainvoke(initial_state)
        return result
