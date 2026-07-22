from __future__ import annotations
from dip.Config.config import config
"""LangGraph adapter for durable assessment graph execution.

When langgraph is installed, this provides a StateGraph-based implementation
of the assessment pipeline with checkpointing and human-in-the-loop support.
"""

import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

# Optional import
try:
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint.memory import MemorySaver
    LANGGRAPH_AVAILABLE = True
except Exception:
    LANGGRAPH_AVAILABLE = False

from .contracts import AssessmentGoal, BlackboardEvent, PipelinePhase
from .assessment_graph import AssessmentBlackboard, HeadOfStatePipelineGraph


class LangGraphState(BaseModel):
    """State schema for LangGraph execution."""
    model_config = {"arbitrary_types_allowed": True}
    goal: AssessmentGoal
    blackboard: AssessmentBlackboard
    current_phase: str = PipelinePhase.GOAL_INTAKE
    state_context: Optional[Any] = None
    session: Optional[Any] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class LangGraphAdapter:
    """LangGraph-backed assessment graph with checkpointing."""

    def __init__(self, checkpoint_dir: Optional[str] = None):
        if not LANGGRAPH_AVAILABLE:
            raise RuntimeError("langgraph not installed. Install with: pip install langgraph")
        self.checkpoint_dir = checkpoint_dir
        self.checkpointer = MemorySaver()
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the assessment StateGraph."""
        workflow = StateGraph(LangGraphState)

        # Add nodes for each phase
        workflow.add_node("goal_intake", self._goal_intake_node)
        workflow.add_node("collection", self._collection_node)
        workflow.add_node("fuzzy_projection", self._fuzzy_projection_node)
        workflow.add_node("sre", self._sre_node)
        workflow.add_node("council", self._council_node)
        workflow.add_node("investigation", self._investigation_node)
        workflow.add_node("gate", self._gate_node)
        workflow.add_node("report", self._report_node)
        workflow.add_node("learning", self._learning_node)

        # Define edges
        workflow.set_entry_point("goal_intake")
        workflow.add_edge("goal_intake", "collection")
        workflow.add_edge("collection", "fuzzy_projection")
        workflow.add_edge("fuzzy_projection", "sre")
        workflow.add_edge("sre", "council")
        workflow.add_edge("council", "investigation")
        workflow.add_edge("investigation", "gate")
        workflow.add_edge("gate", "report")
        workflow.add_edge("report", "learning")
        workflow.add_edge("learning", END)

        # Add conditional edges for human-in-the-loop
        workflow.add_conditional_edges(
            "gate",
            self._gate_condition,
            {
                "human_review": "report",
                "continue": "report",
            }
        )

        return workflow.compile(checkpointer=self.checkpointer)

    async def _goal_intake_node(self, state: LangGraphState) -> LangGraphState:
        state.blackboard.post(PipelinePhase.GOAL_INTAKE, "goal.created", {
            "objective": state.goal.objective,
            "country": state.goal.country,
        })
        state.current_phase = PipelinePhase.GOAL_INTAKE
        return state

    async def _collection_node(self, state: LangGraphState) -> LangGraphState:
        state.blackboard.post(PipelinePhase.COLLECTION, "collection.started", {
            "country": state.goal.country,
        })
        # Collection logic would go here
        state.current_phase = PipelinePhase.COLLECTION
        return state

    async def _fuzzy_projection_node(self, state: LangGraphState) -> LangGraphState:
        state.blackboard.post(PipelinePhase.FUZZY_PROJECTION, "fuzzy_projection.started", {})
        state.current_phase = PipelinePhase.FUZZY_PROJECTION
        return state

    async def _sre_node(self, state: LangGraphState) -> LangGraphState:
        state.blackboard.post(PipelinePhase.SRE, "sre.started", {})
        # SRE logic would go here
        state.current_phase = PipelinePhase.SRE
        return state

    async def _council_node(self, state: LangGraphState) -> LangGraphState:
        state.blackboard.post(PipelinePhase.COUNCIL, "council.started", {})
        # Council logic would go here
        state.current_phase = PipelinePhase.COUNCIL
        return state

    async def _investigation_node(self, state: LangGraphState) -> LangGraphState:
        state.blackboard.post(PipelinePhase.INVESTIGATION, "investigation.started", {})
        state.current_phase = PipelinePhase.INVESTIGATION
        return state

    async def _gate_node(self, state: LangGraphState) -> LangGraphState:
        state.blackboard.post(PipelinePhase.GATE, "gate.started", {})
        state.current_phase = PipelinePhase.GATE
        return state

    async def _report_node(self, state: LangGraphState) -> LangGraphState:
        state.blackboard.post(PipelinePhase.REPORT, "report.started", {})
        state.current_phase = PipelinePhase.REPORT
        return state

    async def _learning_node(self, state: LangGraphState) -> LangGraphState:
        state.blackboard.post(PipelinePhase.LEARNING, "learning.started", {})
        state.current_phase = PipelinePhase.LEARNING
        return state

    def _gate_condition(self, state: LangGraphState) -> str:
        """Determine if human review is needed."""
        # Check if verification failed or threat is high with low confidence
        if state.result and state.result.get("status") == "HUMAN_REVIEW":
            return "human_review"
        return "continue"

    async def run(self, goal: AssessmentGoal, blackboard: AssessmentBlackboard) -> Dict[str, Any]:
        """Run the assessment graph."""
        initial_state = LangGraphState(goal=goal, blackboard=blackboard)
        config = {"configurable": {"thread_id": goal.trace_id}}
        final_state = await self.graph.ainvoke(initial_state, config=config)
        return final_state.get("result", {})


def create_langgraph_adapter(checkpoint_dir: Optional[str] = None) -> Optional[LangGraphAdapter]:
    """Factory to create LangGraph adapter if available."""
    if not LANGGRAPH_AVAILABLE:
        return None
    if not config.DIP_LANGGRAPH_ENABLED:
            return None
    return LangGraphAdapter(checkpoint_dir=checkpoint_dir)