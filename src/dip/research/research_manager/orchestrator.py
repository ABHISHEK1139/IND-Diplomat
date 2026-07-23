import logging
from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict

logger = logging.getLogger("DIP3.Layer11.ResearchOrchestrator")

class ResearchState(TypedDict):
    goal: str
    sub_queries: List[str]
    literature: List[Dict[str, Any]]
    hypotheses: List[str]
    is_novel: bool

class AutonomousResearchManager:
    def __init__(self):
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(ResearchState)
        
        # Define nodes
        workflow.add_node("decompose", self._decompose)
        workflow.add_node("search", self._search)
        workflow.add_node("hypothesize", self._hypothesize)
        workflow.add_node("check_novelty", self._check_novelty)

        # Define edges
        workflow.set_entry_point("decompose")
        workflow.add_edge("decompose", "search")
        workflow.add_edge("search", "hypothesize")
        workflow.add_edge("hypothesize", "check_novelty")
        
        # Conditional edge: loop back if not novel
        def _route(state: ResearchState):
            if state.get("is_novel"):
                return END
            return "search"
            
        workflow.add_conditional_edges("check_novelty", _route)
        return workflow.compile()

    def _decompose(self, state: ResearchState):
        logger.info(f"Decomposing goal: {state['goal']}")
        return {"sub_queries": ["search_query_1", "search_query_2"]}

    def _search(self, state: ResearchState):
        logger.info(f"Searching literature for: {state.get('sub_queries')}")
        return {"literature": [{"title": "Mock Paper", "abstract": "Mock data"}]}

    def _hypothesize(self, state: ResearchState):
        logger.info("Formulating new hypotheses based on literature.")
        return {"hypotheses": ["Hypothesis A"]}

    def _check_novelty(self, state: ResearchState):
        logger.info("Checking novelty against World Model.")
        return {"is_novel": True} # Mocked as novel to break loop

    def run(self, goal: str):
        initial_state = {"goal": goal, "sub_queries": [], "literature": [], "hypotheses": [], "is_novel": False}
        return self.graph.invoke(initial_state)
