"""
Planner Workflow — LangGraph Orchestration
===========================================

Orchestrates the investigation planning phase as a state graph:
Understand -> Extract Scope -> Expand -> Choose Template -> Generate Plan
"""

import logging
from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime, timezone

try:
    from langgraph.graph import StateGraph, END
except ImportError:
    StateGraph, END = None, None

from dip.core.schema import (
    Investigation, UserObjective, InvestigationScope, 
    CollectionPlan, CollectionNeed
)
from dip.layer0_planning.scope_detector import ScopeDetector
from dip.layer0_planning.objective_parser import ObjectiveParser
from dip.layer0_planning.query_expander import QueryExpander
from dip.layer0_planning.template_selector import TemplateSelector
from dip.layer0_planning.planner_memory import PlannerMemory
from dip.Config.config import config
from dip.layer10_telemetry.llm_tracer import tracer

logger = logging.getLogger("Layer0.Workflow")


# Define the State for LangGraph
class PlannerState(TypedDict):
    query: str
    owner: str
    investigation_id: str
    objective: Optional[Dict[str, Any]]
    scope: Optional[Dict[str, List[str]]]
    expanded_queries: Optional[List[str]]
    template: Optional[Dict[str, Any]]
    past_plans: Optional[List[Dict]]
    final_plan: Optional[CollectionPlan]
    investigation_obj: Optional[Investigation]


class PlanningWorkflow:
    """
    Builds and executes the LangGraph workflow for Investigation Planning.
    Replaces the monolithic LLM calls with specialized OSS tasks.
    """

    def __init__(self):
        self.scope_detector = ScopeDetector()
        self.objective_parser = ObjectiveParser()
        self.query_expander = QueryExpander()
        self.template_selector = TemplateSelector()
        self.memory = PlannerMemory()
        
        if StateGraph:
            self.graph = self._build_graph()
        else:
            self.graph = None

    def _build_graph(self):
        workflow = StateGraph(PlannerState)
        
        # Add nodes
        workflow.add_node("understand", self.node_understand)
        workflow.add_node("extract_scope", self.node_extract_scope)
        workflow.add_node("expand_query", self.node_expand_query)
        workflow.add_node("choose_template", self.node_choose_template)
        workflow.add_node("generate_plan", self.node_generate_plan)
        
        # Add edges
        workflow.set_entry_point("understand")
        workflow.add_edge("understand", "extract_scope")
        workflow.add_edge("extract_scope", "expand_query")
        workflow.add_edge("expand_query", "choose_template")
        workflow.add_edge("choose_template", "generate_plan")
        workflow.add_edge("generate_plan", END)
        
        return workflow.compile()

    def node_understand(self, state: PlannerState) -> PlannerState:
        """Parse objective and search memory."""
        query = state["query"]
        logger.info(f"Node: understand for query '{query}'")
        
        objective = self.objective_parser.parse(query)
        past_plans = self.memory.search_similar_plans(query)
        
        state["objective"] = objective
        state["past_plans"] = past_plans
        return state

    def node_extract_scope(self, state: PlannerState) -> PlannerState:
        """Extract scope entities using GLiNER."""
        logger.info("Node: extract_scope")
        scope = self.scope_detector.detect(state["query"])
        state["scope"] = scope
        return state

    def node_expand_query(self, state: PlannerState) -> PlannerState:
        """Expand queries using KeyBERT."""
        logger.info("Node: expand_query")
        # Base text is query + objective
        text = f"{state['query']} {state['objective'].get('objective', '')}"
        expanded = self.query_expander.expand(text)
        state["expanded_queries"] = expanded
        return state

    def node_choose_template(self, state: PlannerState) -> PlannerState:
        """Select investigation template."""
        logger.info("Node: choose_template")
        domains = state["scope"].get("domains", [])
        template = self.template_selector.select(domains)
        state["template"] = template
        return state

    def node_generate_plan(self, state: PlannerState) -> PlannerState:
        """Assemble the final investigation object and collection plan using main LLM."""
        logger.info("Node: generate_plan")
        
        # Use the main API LLM to finalize the plan based on all the structured context gathered
        # by the OSS tools.
        obj_data = state["objective"]
        scope_data = state["scope"]
        template = state["template"]
        
        # Construct the final schema objects
        user_obj = UserObjective(
            objective=obj_data.get("objective", state["query"]),
            decision_support_type=obj_data.get("decision_support_type", "Assessment"),
            time_horizon=obj_data.get("time_horizon", "Unknown"),
            depth=template.get("depth", "Standard"),
            output_format="Dossier"
        )
        
        inv_scope = InvestigationScope(
            countries=scope_data.get("countries", []),
            domains=scope_data.get("domains", []),
            companies=scope_data.get("companies", []),
            government_bodies=scope_data.get("organizations", []),
            key_actors=scope_data.get("key_actors", []),
            keywords=state["expanded_queries"]
        )
        
        # Build collection needs based on template
        needs = []
        for src in template.get("needs", ["News"]):
            needs.append(CollectionNeed(
                source_type=src,
                priority="High",
                description=f"Collect {src} data for {inv_scope.domains}"
            ))
            
        plan = CollectionPlan(
            needs=needs,
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_sources_planned=len(needs)
        )
        
        state["final_plan"] = plan
        
        # Assemble the root Investigation object
        state["investigation_obj"] = Investigation(
            investigation_id=state["investigation_id"],
            title=f"Investigation into {user_obj.objective[:30]}...",
            description=f"Generated via OSS Workflow.",
            original_query=state["query"],
            owner=state["owner"],
            status="CREATED",
            objective=user_obj,
            scope=inv_scope,
            collection_plan=plan,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat()
        )
        
        # Store in Mem0
        self.memory.store_plan(state["query"], str(template.get("needs", [])))
        
        return state

    async def execute(self, query: str, owner: str, investigation_id: str) -> Investigation:
        """Run the workflow."""
        if not self.graph:
            raise RuntimeError("LangGraph not installed. Workflow disabled.")
            
        initial_state = PlannerState(
            query=query, owner=owner, investigation_id=investigation_id,
            objective=None, scope=None, expanded_queries=None,
            template=None, past_plans=None, final_plan=None, investigation_obj=None
        )
        
        # Execute the graph
        logger.info(f"Starting LangGraph workflow for query: {query}")
        final_state = self.graph.invoke(initial_state)
        
        return final_state["investigation_obj"]
