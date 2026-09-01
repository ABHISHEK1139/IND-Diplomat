"""
DIP 3.0 — Investigation Pipeline Orchestrator (LangGraph)
=========================================================

State-machine-driven pipeline using LangGraph as the master orchestrator.
Every phase transitions the investigation through its lifecycle.
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone
from typing import TypedDict, Dict, Any, List, Optional

from dotenv import load_dotenv

try:
    from langgraph.graph import StateGraph, END
except ImportError:
    StateGraph, END = None, None

from dip.core.schema import TimelineEvent, Investigation
from dip.core.investigation_store import InvestigationStore
from dip.layer0_planning.workflow import PlanningWorkflow
from dip.pipeline.collection.adaptive_collector import AdaptiveCollector
from dip.pipeline.world_model.world.world_model import WorldModel
from dip.pipeline.world_model.world.document_understanding.docling_parser import DoclingParser
from dip.pipeline.world_model.world.entity.gliner_extractor import EntityExtractor
from dip.pipeline.world_model.world.relation.rebel_extractor import RelationExtractor
from dip.pipeline.world_model.world.claims.claim_extractor import ClaimExtractor
from dip.pipeline.deliberation.reasoning.orchestrator import ReasoningOrchestrator
from dip.pipeline.forecasting.forecasting.orchestrator import ForecastingOrchestrator
from dip.pipeline.synthesis.workspace.orchestrator import WorkspaceOrchestrator
from dip.pipeline.memory.learning.orchestrator import LearningOrchestrator
from dip.hitl.review_manager import ReviewManager
from dip.telemetry.dataset_exporter import DatasetExporter
from dip.telemetry.llm_tracer import current_investigation_id
from dip.pipeline.memory.core.investigation_memory import InvestigationMemory

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")
logger = logging.getLogger("DIP3.MasterGraph")

class MasterState(TypedDict):
    query: str
    owner: str
    investigation_id: str
    investigation: Optional[Investigation]
    observations: List[Any]
    world_model: Optional[WorldModel]
    reasoning_results: Dict[str, Any]
    simulation_results: Dict[str, Any]
    workspace_results: Dict[str, Any]
    human_edits: Dict[str, Any]
    eval_metrics: Dict[str, Any]

class MasterOrchestrator:
    def __init__(self):
        self.store = InvestigationStore()
        self.memory = InvestigationMemory()
        self.planner = PlanningWorkflow()
        self.collector = AdaptiveCollector(store=self.store)
        self.world_model = WorldModel()
        self.docling_parser = DoclingParser()
        self.reasoning = ReasoningOrchestrator()
        self.forecasting = ForecastingOrchestrator()
        self.workspace = WorkspaceOrchestrator()
        self.learning = LearningOrchestrator()
        
        self.entity_extractor = EntityExtractor()
        self.relation_extractor = RelationExtractor()
        self.claim_extractor = ClaimExtractor()
        
        self.hitl = None # Initialized in node_planning

        if StateGraph:
            self.graph = self._build_graph()
        else:
            self.graph = None

    def _build_graph(self):
        workflow = StateGraph(MasterState)
        
        workflow.add_node("node_planning", self.node_planning)
        workflow.add_node("node_collection", self.node_collection)
        workflow.add_node("node_world_model", self.node_world_model)
        workflow.add_node("node_reasoning", self.node_reasoning)
        workflow.add_node("node_forecasting", self.node_forecasting)
        workflow.add_node("node_workspace", self.node_workspace)
        workflow.add_node("node_learning", self.node_learning)
        workflow.add_node("node_finalize", self.node_finalize)

        workflow.set_entry_point("node_planning")
        workflow.add_edge("node_planning", "node_collection")
        workflow.add_edge("node_collection", "node_world_model")
        workflow.add_edge("node_world_model", "node_reasoning")
        workflow.add_edge("node_reasoning", "node_forecasting")
        workflow.add_edge("node_forecasting", "node_workspace")
        workflow.add_edge("node_workspace", "node_learning")
        workflow.add_edge("node_learning", "node_finalize")
        workflow.add_edge("node_finalize", END)
        
        return workflow.compile()

    async def node_planning(self, state: MasterState) -> MasterState:
        logger.info("=" * 60)
        logger.info("PHASE 0: INVESTIGATION PLANNING")
        logger.info("=" * 60)
        
        investigation = await self.planner.execute(state["query"], state["owner"], state["investigation_id"])
        self.store.create(investigation)
        self.store.transition(investigation, "PLANNING")
        current_investigation_id.set(investigation.investigation_id)
        
        self.hitl = ReviewManager(investigation.investigation_id)
        investigation.objective = self.hitl.checkpoint("Investigation Objective", investigation.objective)
        investigation.scope = self.hitl.checkpoint("Investigation Scope", investigation.scope)
        self.memory.save_investigation(investigation)

        logger.info(f"Investigation: {investigation.investigation_id}")
        logger.info(f"Title:         {investigation.title}")
        
        state["investigation"] = investigation
        return state

    async def node_collection(self, state: MasterState) -> MasterState:
        logger.info("=" * 60)
        logger.info("PHASE 1: ADAPTIVE COLLECTION")
        logger.info("=" * 60)
        
        investigation = state["investigation"]
        self.store.transition(investigation, "COLLECTING")
        observations = await self.collector.collect(investigation)
        
        investigation.evidence_count = len(observations)
        self.store.save(investigation)
        self.store.append_timeline(
            investigation.investigation_id,
            TimelineEvent(
                timestamp=datetime.now(timezone.utc).isoformat(),
                event_type="DATA_COLLECTED",
                description=f"Collected {len(observations)} raw observations",
                layer="Layer1",
            )
        )
        logger.info(f"Collected {len(observations)} raw observations.")
        
        state["observations"] = observations
        return state

    async def node_world_model(self, state: MasterState) -> MasterState:
        logger.info("=" * 60)
        logger.info("PHASE 2 & 3: WORLD MODEL CONSTRUCTION")
        logger.info("=" * 60)
        
        investigation = state["investigation"]
        self.store.transition(investigation, "ANALYZING")
        
        all_claims = []
        for obs in state["observations"]:
            content = obs.content
            
            # If the observation is a file path (PDF/DOCX), parse it with Docling first
            if isinstance(content, str) and (content.endswith(".pdf") or content.endswith(".docx")):
                content = self.docling_parser.parse_document(content)
                
            claims = self.claim_extractor.extract(content, source_context=obs.source_type)
            all_claims.extend(claims)
            for claim in claims:
                subj, pred, obj = claim.get("subject"), claim.get("predicate"), claim.get("object")
                if subj and pred and obj:
                    self.world_model.register_claim(subj, pred, obj, obs.observation_id, claim.get("confidence_extracted", 1.0))
        
        investigation.signal_count = len(all_claims)
        self.store.save(investigation)
        
        countries = getattr(investigation.scope, "countries", []) or []
        target = countries[0] if countries else investigation.title
        wm_state = self.world_model.get_beliefs_about(target)
        self.store.save_world_model(investigation.investigation_id, wm_state, version=investigation.version)
        
        if self.hitl:
            wm_state = self.hitl.checkpoint("World Model State", wm_state)
            
        state["world_model"] = self.world_model
        return state

    async def node_reasoning(self, state: MasterState) -> MasterState:
        logger.info("=" * 60)
        logger.info("PHASE 4: MULTI-EXPERT REASONING")
        logger.info("=" * 60)
        
        investigation = state["investigation"]
        reasoning_results = await self.reasoning.run(
            world_model=state["world_model"], 
            topic=investigation.objective.objective, 
            domains=investigation.scope.domains,
            inv_id=investigation.investigation_id
        )
        
        if self.hitl:
            reasoning_results = self.hitl.checkpoint("Reasoning & Consensus Review", reasoning_results)
            
        investigation.hypothesis_count = len(reasoning_results.get("hypotheses", []))
        self.store.save_hypotheses(investigation.investigation_id, reasoning_results.get("hypotheses", []))
        self.store.save(investigation)
        
        self.store.append_timeline(
            investigation.investigation_id,
            TimelineEvent(
                timestamp=datetime.now(timezone.utc).isoformat(),
                event_type="ANALYSIS_COMPLETE",
                description=f"{investigation.hypothesis_count} expert hypotheses generated",
                layer="Layer4",
            )
        )
        
        state["reasoning_results"] = reasoning_results
        return state

    async def node_forecasting(self, state: MasterState) -> MasterState:
        logger.info("=" * 60)
        logger.info("PHASE 5: FORECASTING & SIMULATION")
        logger.info("=" * 60)
        
        investigation = state["investigation"]
        self.store.transition(investigation, "FORECASTING")
        
        simulation_results = await self.forecasting.run(
            world_model=state["world_model"],
            reasoning_results=state["reasoning_results"],
            topic=investigation.objective.objective
        )
        
        investigation.metadata["simulation"] = {
            "scenarios": len(simulation_results.get("scenarios", [])),
            "risk_profile": simulation_results.get("risk_profile", {})
        }
        self.store.save(investigation)
        
        state["simulation_results"] = simulation_results
        return state

    async def node_workspace(self, state: MasterState) -> MasterState:
        logger.info("=" * 60)
        logger.info("PHASE 6: INTELLIGENCE DOSSIER & WORKSPACE")
        logger.info("=" * 60)
        
        investigation = state["investigation"]
        self.store.transition(investigation, "REPORTING")
        
        workspace_results = await self.workspace.run(
            investigation=investigation,
            simulation_results=state["simulation_results"]
        )
        
        investigation.metadata["workspace"] = {
            "metrics": workspace_results.get("metrics"),
            "dossier_export": workspace_results.get("export_path")
        }
        
        if self.hitl:
            investigation.metadata["workspace"], state["human_edits"] = self.hitl.checkpoint_with_edits(
                "Final Dossier Review", investigation.metadata["workspace"]
            )
            
        investigation.reports_generated += 1
        self.store.save(investigation)
        
        state["workspace_results"] = workspace_results
        return state

    async def node_learning(self, state: MasterState) -> MasterState:
        logger.info("=" * 60)
        logger.info("PHASE 7: SELF-EVOLUTION & LEARNING LOOP")
        logger.info("=" * 60)
        
        investigation = state["investigation"]
        
        # Build context from observations for evaluation
        context = []
        for obs in state.get("observations", []):
            if isinstance(obs.content, str):
                context.append(obs.content)
                
        eval_metrics = await self.learning.run_learning_loop(
            investigation=investigation,
            dossier=state.get("workspace_results", {}).get("dossier", {}),
            query=state["query"],
            context=context,
            human_edits=state.get("human_edits", {})
        )
        
        investigation.metadata["evaluation"] = eval_metrics
        self.store.save(investigation)
        
        state["eval_metrics"] = eval_metrics
        return state

    async def node_finalize(self, state: MasterState) -> MasterState:
        logger.info("=" * 60)
        logger.info("FINALIZE: PERSIST & EXPORT")
        logger.info("=" * 60)
        
        investigation = state["investigation"]
        investigation.world_model_id = f"WM-{investigation.investigation_id}-v{investigation.version}"
        
        self.store.snapshot_version(investigation)
        self.store.transition(investigation, "MONITORING")
        self.memory.save_investigation(investigation)
        
        exporter = DatasetExporter()
        sft_file = exporter.export_sft(investigation)
        dpo_file = exporter.export_dpo(investigation)
        
        self.store.append_timeline(
            investigation.investigation_id,
            TimelineEvent(
                timestamp=datetime.now(timezone.utc).isoformat(),
                event_type="PIPELINE_COMPLETE",
                description="Full investigation pipeline completed",
                layer="Pipeline",
            )
        )
        
        logger.info("=" * 60)
        logger.info("INVESTIGATION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"ID:              {investigation.investigation_id}")
        logger.info(f"Title:           {investigation.title}")
        logger.info(f"Status:          {investigation.status}")
        logger.info(f"Folder:          investigations/{investigation.investigation_id}/")
        logger.info("=" * 60)
        
        return state


async def run_investigation(query: str, owner: str = "default"):
    """Entry point for testing the LangGraph Pipeline"""
    load_dotenv()
    
    now = datetime.now(timezone.utc)
    inv_id = f"INV-{now.strftime('%Y%m%d-%H%M%S')}"
    
    orchestrator = MasterOrchestrator()
    if not orchestrator.graph:
        logger.error("LangGraph not available. Aborting.")
        return
        
    initial_state = MasterState(
        query=query,
        owner=owner,
        investigation_id=inv_id,
        investigation=None,
        observations=[],
        world_model=None,
        reasoning_results={},
        simulation_results={},
        workspace_results={},
        human_edits={},
        eval_metrics={}
    )
    
    final_state = await orchestrator.graph.ainvoke(initial_state)
    return final_state["investigation"]


if __name__ == "__main__":
    test_query = "Analyze India's AI ecosystem and its potential to become a global AI leader by 2035."
    if len(sys.argv) > 1:
        test_query = " ".join(sys.argv[1:])
    asyncio.run(run_investigation(test_query))
